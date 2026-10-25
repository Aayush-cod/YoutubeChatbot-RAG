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