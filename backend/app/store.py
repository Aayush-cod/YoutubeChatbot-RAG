from collections import OrderedDict
from functools import lru_cache
from threading import Lock
from typing import List, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from .config import get_settings


@lru_cache
def get_embeddings() -> HuggingFaceEmbeddings:
    """Load the embedding model once, then reuse it."""
    return HuggingFaceEmbeddings(model_name=get_settings().embedding_model)


# video_id -> FAISS index. OrderedDict remembers insertion order,
# so the first item is always the least recently used.
_stores: "OrderedDict[str, FAISS]" = OrderedDict()
_lock = Lock()


def has_video(video_id: str) -> bool:
    with _lock:
        return video_id in _stores


def add_video(video_id: str, chunks: List[Document]) -> None:
    """Embed the chunks, build an index, and remember it."""
    index = FAISS.from_documents(chunks, get_embeddings())
    with _lock:
        _stores[video_id] = index
        _stores.move_to_end(video_id)  # newest goes to the end
        while len(_stores) > get_settings().max_cached_videos:
            _stores.popitem(last=False)  # drop the oldest (front)


def get_store(video_id: str) -> Optional[FAISS]:
    """Return the index for a video, or None if we don't have it."""
    with _lock:
        index = _stores.get(video_id)
        if index is not None:
            _stores.move_to_end(video_id)  # used just now, so keep it
        return index