import pytest
from langchain_core.documents import Document

from app.evaluation import first_hit_rank, overlaps, parse_time, summarize_ranks


def doc(start, end):
    return Document(page_content="x", metadata={"start": start, "end": end})


def test_parse_time():
    assert parse_time("0:07") == 7
    assert parse_time("12:34") == 754
    assert parse_time("1:02:05") == 3725


def test_overlaps():
    assert overlaps(0, 10, 5, 15)
    assert overlaps(5, 15, 0, 10)
    assert overlaps(0, 100, 40, 50)      # one range contains the other
    assert not overlaps(0, 10, 10, 20)   # only touching
    assert not overlaps(0, 10, 20, 30)   # far apart


def test_first_hit_rank():
    docs = [doc(0, 60), doc(100, 160), doc(200, 260)]
    assert first_hit_rank(docs, 110, 130) == 2
    assert first_hit_rank(docs, 500, 520) is None


def test_summarize_ranks():
    result = summarize_ranks([1, 2, None, 4])
    assert result["questions"] == 4
    assert result["hit_rate"] == pytest.approx(0.75)
    assert result["mrr"] == pytest.approx((1 + 1 / 2 + 0 + 1 / 4) / 4)
    assert summarize_ranks([]) == {"questions": 0, "hit_rate": 0.0, "mrr": 0.0}