import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from app import store
from app.config import Settings


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    """Use tiny fake embeddings and start every test with an empty cache."""
    monkeypatch.setattr(store, "get_embeddings", lambda: DeterministicFakeEmbedding(size=32))
    store._stores.clear()
    yield
    store._stores.clear()


def docs(n=3):
    return [Document(page_content=f"chunk {i}", metadata={"start": i}) for i in range(n)]


def test_missing_video_returns_none():
    assert store.get_store("nope") is None
    assert not store.has_video("nope")


def test_add_then_search():
    store.add_video("vid1", docs())
    assert store.has_video("vid1")
    results = store.get_store("vid1").similarity_search("chunk 1", k=2)
    assert len(results) == 2


def test_oldest_video_is_evicted(monkeypatch):
    monkeypatch.setattr(store, "get_settings", lambda: Settings(max_cached_videos=2))
    store.add_video("a", docs())
    store.add_video("b", docs())
    store.add_video("c", docs())
    assert not store.has_video("a")
    assert store.has_video("b") and store.has_video("c")


def test_recently_used_video_is_kept(monkeypatch):
    monkeypatch.setattr(store, "get_settings", lambda: Settings(max_cached_videos=2))
    store.add_video("a", docs())
    store.add_video("b", docs())
    store.get_store("a")            # use "a", so "b" is now the oldest
    store.add_video("c", docs())
    assert store.has_video("a")
    assert not store.has_video("b")