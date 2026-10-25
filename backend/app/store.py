from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from typing import List, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from .config import get_settings

from .schemas import VideoSummary

@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    """Load the embedding model once, then reuse it."""
    return HuggingFaceEmbeddings(model_name=get_settings().embedding_model)


@dataclass
class VideoEntry:
    """Everything we remember about one video."""
    index: FAISS
    chunks: List[Document]
    summary: Optional[VideoSummary] = None


# video_id -> VideoEntry. The first item is always the least recently used.
_stores: "OrderedDict[str, VideoEntry]" = OrderedDict()
_lock = Lock()


def has_video(video_id: str) -> bool:
    with _lock:
        return video_id in _stores


def add_video(video_id: str, chunks: List[Document]) -> None:
    """Embed the chunks, build an index, and remember both."""
    index = FAISS.from_documents(chunks, get_embeddings())
    with _lock:
        _stores[video_id] = VideoEntry(index=index, chunks=chunks)
        _stores.move_to_end(video_id)
        while len(_stores) > get_settings().max_cached_videos:
            _stores.popitem(last=False)


def _get_entry(video_id: str) -> Optional[VideoEntry]:
    with _lock:
        entry = _stores.get(video_id)
        if entry is not None:
            _stores.move_to_end(video_id)  # used just now, so keep it
        return entry


def get_store(video_id: str) -> Optional[FAISS]:
    entry = _get_entry(video_id)
    return entry.index if entry else None


def get_chunks(video_id: str) -> Optional[List[Document]]:
    entry = _get_entry(video_id)
    return entry.chunks if entry else None

def get_summary(video_id: str) -> Optional[VideoSummary]:
    entry = _get_entry(video_id)
    return entry.summary if entry else None


def set_summary(video_id: str, summary: VideoSummary) -> None:
    with _lock:
        entry = _stores.get(video_id)
        if entry is not None:
            entry.summary = summary