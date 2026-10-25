from functools import lru_cache
from typing import List

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from .rag import get_llm
from .schemas import VideoSummary

SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You summarize a YouTube video from its transcript.
Each line starts with a number in square brackets: that is the time in SECONDS where the line begins.

Produce:
- summary: 3 to 5 sentences.
- key_points: 4 to 8 important points. For each, set timestamp_seconds to the bracket number
  of the line where it is discussed.
- topics: 3 to 6 short topic tags.

Use only the transcript. Do not invent anything.""",
        ),
        ("human", "{transcript}"),
    ]
)


def format_transcript(docs: List[Document]) -> str:
    """One line per chunk, labelled with its start time in seconds."""
    return "\n".join(f"[{d.metadata['start']}] {d.page_content}" for d in docs)


@lru_cache
def get_summary_llm():
    """The Groq model, forced to reply in the VideoSummary shape."""
    return get_llm().with_structured_output(VideoSummary)


def summarize_docs(docs: List[Document], structured_llm=None) -> VideoSummary:
    chain = SUMMARY_PROMPT | (structured_llm or get_summary_llm())
    return chain.invoke({"transcript": format_transcript(docs)})




MAX_BATCH_CHARS = 12_000  # roughly 3,000 tokens per batch

REDUCE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are given partial summaries of consecutive parts of ONE YouTube video.
Each key point starts with its time in SECONDS in square brackets.

Combine them into a single summary of the whole video:
- summary: 3 to 5 sentences about the whole video.
- key_points: the 4 to 8 most important points overall. Keep each point's timestamp_seconds
  exactly as given in the partial summaries.
- topics: 3 to 6 short topic tags.

Use only the partial summaries. Do not invent anything.""",
        ),
        ("human", "{partials}"),
    ]
)


def group_docs(docs: List[Document], max_chars: int) -> List[List[Document]]:
    """Split chunks into batches whose total text stays under max_chars."""
    batches: List[List[Document]] = []
    current: List[Document] = []
    size = 0
    for d in docs:
        n = len(d.page_content)
        if current and size + n > max_chars:
            batches.append(current)
            current, size = [], 0
        current.append(d)
        size += n
    if current:
        batches.append(current)
    return batches


def format_partials(parts: List[VideoSummary]) -> str:
    """Turn partial summaries into text for the reduce step."""
    blocks = []
    for i, p in enumerate(parts, start=1):
        lines = [f"Part {i}:", f"Summary: {p.summary}", "Key points:"]
        for kp in p.key_points:
            lines.append(f"- [{kp.timestamp_seconds}] {kp.point}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def summarize_video(
    docs: List[Document],
    structured_llm=None,
    max_batch_chars: int = MAX_BATCH_CHARS,
) -> VideoSummary:
    """Summarize a whole video, using map-reduce when it is too long for one call."""
    batches = group_docs(docs, max_batch_chars)
    if len(batches) <= 1:
        return summarize_docs(docs, structured_llm)

    partials = [summarize_docs(batch, structured_llm) for batch in batches]  # MAP
    chain = REDUCE_PROMPT | (structured_llm or get_summary_llm())            # REDUCE
    return chain.invoke({"partials": format_partials(partials)})