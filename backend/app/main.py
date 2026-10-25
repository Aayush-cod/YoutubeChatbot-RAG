from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import store
from .chunking import build_chunks
from .config import get_settings
from .schemas import IngestRequest, IngestResponse, SummaryRequest, VideoSummary
from .summarize import summarize_video

app = FastAPI(title="YouTube RAG API")

# Browsers block web pages from calling other websites unless the server allows it (CORS).
# "*" is fine while developing; we'll tighten it before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest):
    # Already processed this video? Reuse it instead of embedding again.
    existing = store.get_chunks(req.video_id)
    if existing is not None:
        return IngestResponse(video_id=req.video_id, chunks=len(existing), cached=True)

    settings = get_settings()
    chunks = build_chunks(req.segments, settings.chunk_chars, settings.chunk_overlap_chars)
    if not chunks:
        raise HTTPException(status_code=400, detail="Transcript has no usable text.")

    store.add_video(req.video_id, chunks)
    return IngestResponse(video_id=req.video_id, chunks=len(chunks), cached=False)

@app.post("/summary", response_model=VideoSummary)
def summary(req: SummaryRequest):
    chunks = store.get_chunks(req.video_id)
    if chunks is None:
        raise HTTPException(
            status_code=404,
            detail="Video not found. Send its transcript to /ingest first.",
        )
    return summarize_video(chunks)

