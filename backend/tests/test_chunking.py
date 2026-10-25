from app.chunking import build_chunks, fmt_time
from app.schemas import Segment


def make_segments(n=200):
    return [
        Segment(text=f"sentence number {i} about topic {i % 5}", start=i * 3.0, duration=3.0)
        for i in range(n)
    ]


def test_empty_input_gives_no_chunks():
    assert build_chunks([], 1000, 200) == []


def test_single_segment():
    chunks = build_chunks([Segment(text="hello", start=5)], 1000, 200)
    assert len(chunks) == 1
    assert chunks[0].page_content == "hello"
    assert chunks[0].metadata["start"] == 5


def test_blank_segments_are_ignored():
    segs = [Segment(text="   ", start=0), Segment(text="real", start=1)]
    chunks = build_chunks(segs, 1000, 200)
    assert chunks[0].page_content == "real"
    assert chunks[0].metadata["start"] == 1


def test_chunks_respect_max_size():
    chunks = build_chunks(make_segments(), 1000, 200)
    assert len(chunks) > 3
    assert all(len(c.page_content) <= 1000 for c in chunks)


def test_start_times_increase():
    chunks = build_chunks(make_segments(), 1000, 200)
    starts = [c.metadata["start"] for c in chunks]
    assert starts[0] == 0
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)  # no repeats, so we always move forward


def test_consecutive_chunks_overlap():
    chunks = build_chunks(make_segments(), 1000, 200)
    assert chunks[1].metadata["start"] < chunks[0].metadata["end"]


def test_last_chunk_reaches_end_of_video():
    segs = make_segments()
    chunks = build_chunks(segs, 1000, 200)
    assert chunks[-1].metadata["end"] == int(segs[-1].start + segs[-1].duration)


def test_fmt_time():
    assert fmt_time(65) == "1:05"
    assert fmt_time(3725) == "1:02:05"