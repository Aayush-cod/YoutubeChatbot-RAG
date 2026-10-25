from functools import lru_cache
from typing import List

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from .chunking import fmt_time
from .config import get_settings
from .store import get_store

SYSTEM_PROMPT = """You answer questions about a YouTube video using ONLY the transcript excerpts below.
Each excerpt starts with its timestamp in square brackets, like [1:05].

Rules:
- If the excerpts do not contain the answer, say the video does not seem to cover it. Do not guess.
- When you state a fact, cite the timestamp it came from, like [1:05].
- Keep answers short and clear.

Transcript excerpts:
{context}"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "{question}"),
    ]
)


class VideoNotFound(Exception):
    """Raised when we have no stored transcript for a video."""


def format_context(docs: List[Document]) -> str:
    """Turn retrieved chunks into text the model can read, with timestamps."""
    return "\n\n".join(f"[{fmt_time(d.metadata['start'])}] {d.page_content}" for d in docs)


def retrieve(video_id: str, question: str) -> List[Document]:
    """Find the top_k chunks of this video closest to the question."""
    store = get_store(video_id)
    if store is None:
        raise VideoNotFound(video_id)
    return store.similarity_search(question, k=get_settings().top_k)


@lru_cache
def get_llm() -> ChatGroq:
    settings = get_settings()
    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0.2,
    )


def build_chain(llm=None):
    """prompt -> model -> plain string. Pass a fake llm in tests."""
    return PROMPT | (llm or get_llm()) | StrOutputParser()