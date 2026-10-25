import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding

from app import store
from app.main import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(store, "get_embeddings", lambda: DeterministicFakeEmbedding(size=32))
    store._stores.clear()
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