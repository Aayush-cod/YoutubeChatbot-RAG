from functools import lru_cache

from langchain_core.documents import Document

from .config import get_settings


@lru_cache
def get_reranker():
    """Load the cross-encoder once (a ~90 MB model, downloaded the first time)."""
    from sentence_transformers import (
        CrossEncoder,  # imported here so the app starts fast
    )

    return CrossEncoder(get_settings().reranker_model)


def rerank(question: str, docs: list[Document], top_n: int, model=None) -> list[Document]:
    """Score every chunk against the question and keep the best top_n."""
    if not docs:
        return []
    model = model or get_reranker()
    scores = model.predict([(question, d.page_content) for d in docs])
    ranked = sorted(zip(scores, docs), key=lambda pair: pair[0], reverse=True)
    return [d for _, d in ranked[:top_n]]