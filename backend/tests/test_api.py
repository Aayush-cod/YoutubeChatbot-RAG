import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding

from app import main, store
from app.main import app
from app.schemas import KeyPoint, VideoSummary


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