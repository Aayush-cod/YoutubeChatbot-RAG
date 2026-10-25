from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from app import summarize
from app.schemas import KeyPoint, VideoSummary



def test_format_transcript_uses_seconds():
    docs = [
        Document(page_content="intro", metadata={"start": 0, "end": 5}),
        Document(page_content="main idea", metadata={"start": 65, "end": 70}),
    ]
    assert summarize.format_transcript(docs) == "[0] intro\n[65] main idea"


def test_summarize_returns_structured_result():
    expected = VideoSummary(
        summary="A short talk.",
        key_points=[KeyPoint(point="Main idea", timestamp_seconds=65)],
        topics=["intro"],
    )
    fake = RunnableLambda(lambda _prompt: expected)  # stands in for the model
    docs = [Document(page_content="hi", metadata={"start": 0, "end": 5})]
    assert summarize.summarize_docs(docs, structured_llm=fake) == expected



    

def make_docs(n, size=10):
    return [Document(page_content="x" * size, metadata={"start": i * 10, "end": i * 10 + 10}) for i in range(n)]


def test_group_docs_respects_limit():
    assert summarize.group_docs([], 100) == []
    batches = summarize.group_docs(make_docs(5, size=10), max_chars=25)
    assert [len(b) for b in batches] == [2, 2, 1]


def test_group_docs_oversized_doc_gets_its_own_batch():
    batches = summarize.group_docs(make_docs(3, size=100), max_chars=25)
    assert [len(b) for b in batches] == [1, 1, 1]


def test_format_partials():
    part = VideoSummary(
        summary="About pasta.",
        key_points=[KeyPoint(point="Salt the water", timestamp_seconds=10)],
        topics=["cooking"],
    )
    text = summarize.format_partials([part])
    assert "Part 1:" in text and "[10] Salt the water" in text


def fake_model(calls):
    result = VideoSummary(summary="s", key_points=[], topics=[])

    def run(_prompt):
        calls.append(1)
        return result

    return RunnableLambda(run)


def test_short_video_uses_a_single_call():
    calls = []
    summarize.summarize_video(make_docs(3), fake_model(calls), max_batch_chars=1000)
    assert len(calls) == 1


def test_long_video_uses_map_then_reduce():
    calls = []
    summarize.summarize_video(make_docs(6), fake_model(calls), max_batch_chars=25)
    # 6 docs of 10 chars with a 25-char limit = 3 batches -> 3 map calls + 1 reduce call
    assert len(calls) == 4