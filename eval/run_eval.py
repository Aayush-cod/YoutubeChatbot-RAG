"""Measure how often retrieval finds the right part of the video.

Run from the project root:  python eval/run_eval.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))  # so we can import the app package

from app import rag, store  # noqa: E402
from app.chunking import build_chunks, fmt_time  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.evaluation import first_hit_rank, parse_time, summarize_ranks  # noqa: E402
from app.schemas import Segment  # noqa: E402


def main() -> None:
    spec = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
    video_id = spec["video_id"]
    raw = json.loads((ROOT / "eval" / "transcripts" / f"{video_id}.json").read_text(encoding="utf-8"))
    segments = [Segment(**s) for s in raw]

    settings = get_settings()
    chunks = build_chunks(segments, settings.chunk_chars, settings.chunk_overlap_chars)
    print(f"{len(segments)} segments -> {len(chunks)} chunks | top_k={settings.top_k}")
    store.add_video(video_id, chunks)

    ranks = []
    for number, q in enumerate(spec["questions"], start=1):
        win_start, win_end = parse_time(q["start"]), parse_time(q["end"])
        docs = rag.retrieve(video_id, q["question"])  # the same function /chat uses
        rank = first_hit_rank(docs, win_start, win_end)
        ranks.append(rank)

        if rank is None:
            got = ", ".join(fmt_time(d.metadata["start"]) for d in docs)
            print(f"MISS {number:>2}: {q['question']}")
            print(f"        answer is at {q['start']}-{q['end']}, retrieved chunks start at: {got}")
        else:
            print(f"hit  {number:>2}: rank {rank}")

    result = summarize_ranks(ranks)
    print()
    print(f"questions: {result['questions']}")
    print(f"hit rate @{settings.top_k}: {result['hit_rate']:.2f}")
    print(f"MRR:        {result['mrr']:.3f}")


if __name__ == "__main__":
    main()