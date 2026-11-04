from app.rerank import rerank
from langchain_core.documents import Document


class FakeScorer:
    """Scores a chunk by how many words it shares with the question."""

    def predict(self, pairs):
        return [len(set(q.split()) & set(c.split())) for q, c in pairs]


def make_docs(texts):
    return [Document(page_content=t, metadata={"start": i}) for i, t in enumerate(texts)]


def test_best_match_moves_to_the_top():
    docs = make_docs(["cats and dogs", "history of rockets", "byte pair encoding explained"])
    result = rerank("what is byte pair encoding", docs, top_n=3, model=FakeScorer())
    assert result[0].page_content == "byte pair encoding explained"


def test_keeps_only_top_n():
    docs = make_docs(["a b", "a", "a b c", "z"])
    result = rerank("a b c", docs, top_n=2, model=FakeScorer())
    assert len(result) == 2
    assert result[0].page_content == "a b c"


def test_empty_input():
    assert rerank("anything", [], top_n=5, model=FakeScorer()) == []

