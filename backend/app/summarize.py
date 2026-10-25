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