import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from app import main, rag, store
from app.main import app
from app.schemas import KeyPoint, VideoSummary
from app.config import Settings


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(store, "get_embeddings", lambda: DeterministicFakeEmbedding(size=32))
    store._stores.clear()
    main.limiter.reset()
    yield TestClient(app)
    store._stores.clear()


def segments(n=50):
    return [{"text": f"sentence number {i}", "start": i * 3.0, "duration": 3.0} for i in range(n)]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ingest_then_cached(client):
    body = {"video_id": "abcDEF12345", "segments": segments()}
    first = client.post("/ingest", json=body)
    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert first.json()["chunks"] >= 1

    second = client.post("/ingest", json=body)
    assert second.json()["cached"] is True


def test_ingest_rejects_bad_video_id(client):
    r = client.post("/ingest", json={"video_id": "bad id!", "segments": segments()})
    assert r.status_code == 422


def test_ingest_rejects_empty_segment_list(client):
    r = client.post("/ingest", json={"video_id": "abcDEF12345", "segments": []})
    assert r.status_code == 422


def test_ingest_rejects_blank_transcript(client):
    blank = [{"text": "   ", "start": 0}]
    r = client.post("/ingest", json={"video_id": "abcDEF12345", "segments": blank})
    assert r.status_code == 400

def test_summary_for_ingested_video(client, monkeypatch):
    fake = VideoSummary(
        summary="A short talk.",
        key_points=[KeyPoint(point="Main idea", timestamp_seconds=6)],
        topics=["intro"],
    )
    monkeypatch.setattr(main, "summarize_video", lambda chunks: fake)  # no real model call

    client.post("/ingest", json={"video_id": "abcDEF12345", "segments": segments()})
    r = client.post("/summary", json={"video_id": "abcDEF12345"})

    assert r.status_code == 200
    assert r.json()["summary"] == "A short talk."
    assert r.json()["key_points"][0]["timestamp_seconds"] == 6


def test_summary_unknown_video_is_404(client):
    r = client.post("/summary", json={"video_id": "nope12345"})
    assert r.status_code == 404


def test_summary_is_cached(client, monkeypatch):
    calls = []

    def fake(chunks):
        calls.append(1)
        return VideoSummary(summary="s", key_points=[], topics=[])

    monkeypatch.setattr(main, "summarize_video", fake)
    client.post("/ingest", json={"video_id": "abcDEF12345", "segments": segments()})

    client.post("/summary", json={"video_id": "abcDEF12345"})
    client.post("/summary", json={"video_id": "abcDEF12345"})

    assert len(calls) == 1  # the model ran once, the second answer came from memory


def fake_llm():
    return GenericFakeChatModel(messages=iter([AIMessage(content="It is discussed at [0:06].")]))


def read_events(response):
    return [json.loads(line) for line in response.text.splitlines() if line]


def test_chat_streams_sources_tokens_done(client, monkeypatch):
    monkeypatch.setattr(rag, "get_llm", fake_llm)
    client.post("/ingest", json={"video_id": "abcDEF12345", "segments": segments(200)})

    r = client.post("/chat", json={"video_id": "abcDEF12345", "question": "what is discussed?"})

    assert r.status_code == 200
    events = read_events(r)
    assert events[0]["type"] == "sources" and len(events[0]["sources"]) >= 1
    assert events[-1]["type"] == "done"
    text = "".join(e["text"] for e in events if e["type"] == "token")
    assert text.strip() == "It is discussed at [0:06]."


def test_chat_unknown_video_is_404(client):
    r = client.post("/chat", json={"video_id": "nope12345", "question": "hi"})
    assert r.status_code == 404


def test_chat_accepts_history(client, monkeypatch):
    monkeypatch.setattr(rag, "get_llm", fake_llm)
    client.post("/ingest", json={"video_id": "abcDEF12345", "segments": segments(200)})
    history = [
        {"role": "user", "content": "what is this about?"},
        {"role": "assistant", "content": "It is about topics."},
    ]

    r = client.post(
        "/chat",
        json={"video_id": "abcDEF12345", "question": "and the second one?", "history": history},
    )

    assert r.status_code == 200
    assert read_events(r)[-1]["type"] == "done"


def test_chat_reports_model_failure(client, monkeypatch):
    class BrokenChain:
        def stream(self, _inputs):
            raise RuntimeError("boom")

    monkeypatch.setattr(rag, "build_chain", lambda llm=None: BrokenChain())
    client.post("/ingest", json={"video_id": "abcDEF12345", "segments": segments(200)})

    r = client.post("/chat", json={"video_id": "abcDEF12345", "question": "hi"})

    events = read_events(r)
    assert events[-1]["type"] == "error"
    assert all(e["type"] != "done" for e in events)


def test_chat_skips_empty_tokens_and_cleans_brackets(client, monkeypatch):
    class FakeChain:
        def stream(self, _inputs):
            yield from ["", "See ", "【", "0:06", "】", ""]

    monkeypatch.setattr(rag, "build_chain", lambda llm=None: FakeChain())
    client.post("/ingest", json={"video_id": "abcDEF12345", "segments": segments(200)})

    r = client.post("/chat", json={"video_id": "abcDEF12345", "question": "hi"})

    tokens = [e["text"] for e in read_events(r) if e["type"] == "token"]
    assert tokens == ["See ", "[", "0:06", "]"]


def test_chat_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(rate_limit_chat="2/minute"))
    body = {"video_id": "nope12345", "question": "hi"}

    assert client.post("/chat", json=body).status_code == 404  # allowed (video just isn't there)
    assert client.post("/chat", json=body).status_code == 404  # allowed
    assert client.post("/chat", json=body).status_code == 429  # third call in a minute: blocked