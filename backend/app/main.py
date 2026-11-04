import json
import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import rag, store
from .chunking import build_chunks
from .config import get_settings
from .logging_config import setup_logging
from .schemas import (
    ChatRequest,
    IngestRequest,
    IngestResponse,
    SummaryRequest,
    VideoSummary,
)
from .summarize import summarize_video

setup_logging(get_settings().log_level)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)  # one counter per client IP

app = FastAPI(title="YouTube RAG API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Browsers block web pages from calling other websites unless the server allows it (CORS).
# "*" is fine while developing; we'll tighten it before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request) #Pasees the request to the next step i.e endpoint and gets response
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
@limiter.limit(lambda: get_settings().rate_limit_ingest)
def ingest(request: Request, req: IngestRequest):
    # Already processed this video? Reuse it instead of embedding again.
    existing = store.get_chunks(req.video_id)
    if existing is not None:
        logger.info("ingest video=%s chunks=%d cached=True", req.video_id, len(existing))
        return IngestResponse(video_id=req.video_id, chunks=len(existing), cached=True)

    settings = get_settings()
    chunks = build_chunks(req.segments, settings.chunk_chars, settings.chunk_overlap_chars)
    if not chunks:
        raise HTTPException(status_code=400, detail="Transcript has no usable text.")

    store.add_video(req.video_id, chunks)
    logger.info("ingest video=%s chunks=%d cached=False", req.video_id, len(chunks))
    return IngestResponse(video_id=req.video_id, chunks=len(chunks), cached=False)


@app.post("/summary", response_model=VideoSummary)
@limiter.limit(lambda: get_settings().rate_limit_summary)
def summary(request: Request, req: SummaryRequest):
    cached = store.get_summary(req.video_id)
    if cached is not None:
        return cached

    chunks = store.get_chunks(req.video_id)
    if chunks is None:
        raise HTTPException(
            status_code=404,
            detail="Video not found. Send its transcript to /ingest first.",
        )

    result = summarize_video(chunks)
    store.set_summary(req.video_id, result)
    return result

def _line(event: dict) -> str:
    """One NDJSON line: a JSON object followed by a newline."""
    return json.dumps(event) + "\n"


@app.post("/chat")
@limiter.limit(lambda: get_settings().rate_limit_chat)
def chat(request: Request, req: ChatRequest):
    # Retrieve BEFORE streaming starts, so a missing video can still be a proper 404.
    started = time.perf_counter()
    try:
        docs = rag.retrieve(req.video_id, req.question)
    except rag.VideoNotFound:
        raise HTTPException(
            status_code=404,
            detail="Video not found. Send its transcript to /ingest first.",
        )
    logger.info(
        "chat video=%s question_chars=%d retrieved=%d retrieval_ms=%.0f",
        req.video_id,
        len(req.question),
        len(docs),
        (time.perf_counter() - started) * 1000,
    )

    def event_stream():
        yield _line({"type": "sources", "sources": rag.format_sources(docs)})
        try:
            chain = rag.build_chain()
            inputs = {
                "context": rag.format_context(docs),
                "history": rag.to_messages(req.history),
                "question": req.question,
            }
            for token in chain.stream(inputs):
                token = rag.clean_token(token)
                if token:  # skip the empty chunks reasoning models send first
                    yield _line({"type": "token", "text": token})
        except Exception:
            logger.exception("Chat generation failed")
            yield _line({"type": "error", "message": "The model failed. Please try again."})
            return
        yield _line({"type": "done"})

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")