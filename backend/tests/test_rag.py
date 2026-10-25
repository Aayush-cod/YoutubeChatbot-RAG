import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app import rag, store


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(store, "get_embeddings", lambda: DeterministicFakeEmbedding(size=32))
    store._stores.clear()
    yield
    store._stores.clear()


def docs(n=8):
    return [Document(page_content=f"chunk {i}", metadata={"start": i * 10, "end": i * 10 + 10}) for i in range(n)]


def test_format_context_adds_timestamps():
    text = rag.format_context([Document(page_content="hello", metadata={"start": 65, "end": 70})])
    assert text == "[1:05] hello"


def test_retrieve_returns_top_k():
    store.add_video("vid1", docs())
    assert len(rag.retrieve("vid1", "chunk 3")) == 5


def test_retrieve_missing_video_raises():
    with pytest.raises(rag.VideoNotFound):
        rag.retrieve("nope", "anything")


def test_chain_returns_model_text():
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="It is at [0:06].")]))
    chain = rag.build_chain(fake)
    assert chain.invoke({"context": "[0:06] hi", "question": "when?"}) == "It is at [0:06]."