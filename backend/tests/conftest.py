import pytest

from app import rag
from app import rerank as rerank_module


def _forbidden():
    raise RuntimeError("Tests must not load the real reranker model")


@pytest.fixture(autouse=True)
def no_real_reranker(monkeypatch):
    """Tests must never download or run the real cross-encoder."""
    monkeypatch.setattr(rag, "rerank", lambda question, docs, top_n: docs[:top_n])
    monkeypatch.setattr(rerank_module, "get_reranker", _forbidden)