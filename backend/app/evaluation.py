
from langchain_core.documents import Document


def parse_time(text: str) -> int:
    """'12:34' -> 754 seconds, '1:02:05' -> 3725 seconds."""
    seconds = 0
    for part in text.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds


def overlaps(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
    """Do the time ranges a and b share any time? Ranges that only touch don't count."""
    return a_start < b_end and b_start < a_end


def first_hit_rank(docs: list[Document], win_start: int, win_end: int) -> int | None:
    """Position (1 = best) of the first retrieved chunk that overlaps the answer window.
    Returns None if none of them do."""
    for rank, doc in enumerate(docs, start=1):
        if overlaps(doc.metadata["start"], doc.metadata["end"], win_start, win_end):
            return rank
    return None


def summarize_ranks(ranks: list[int | None]) -> dict:
    """Turn one rank per question into the two headline numbers."""
    n = len(ranks)
    if n == 0:
        return {"questions": 0, "hit_rate": 0.0, "mrr": 0.0}
    hits = [r for r in ranks if r is not None]
    return {
        "questions": n,
        "hit_rate": len(hits) / n,
        "mrr": sum(1 / r for r in hits) / n,
    }