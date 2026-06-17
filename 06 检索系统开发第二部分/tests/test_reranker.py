import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from reranker import Reranker  # noqa: E402


class _FakeLookup:
    def preload(self, doc_ids):
        return len(doc_ids)

    def get(self, doc_id):
        data = {
            "PMC111": {"pub_year": 2020, "journal": "Nature"},
            "PMC222": {"pub_year": 2005, "journal": "Unknown Journal"},
        }
        return data.get(doc_id)


class _FakeQuery:
    filters = []


def test_rerank_without_model():
    reranker = Reranker(metadata_lookup=_FakeLookup())
    reranker.score_relevance = lambda q, c: [0.4, 0.9]  # type: ignore[method-assign]

    candidates = [
        {"chunk_id": "a", "doc_id": "PMC222", "source_title": "old", "text": "body"},
        {"chunk_id": "b", "doc_id": "PMC111", "source_title": "new", "text": "body"},
    ]
    out = reranker.rerank("malaria", candidates, top_k=2, query_info=_FakeQuery())
    assert len(out) == 2
    assert out[0]["doc_id"] == "PMC111"
    assert "relevance_score" in out[0]
    assert "final_score" in out[0]
    assert "rerank_explain" in out[0]


def test_rerank_respects_year_hint():
    class Q:
        filters = [type("F", (), {"key": "year_gte", "value": 2015})()]

    reranker = Reranker(metadata_lookup=_FakeLookup())
    reranker.score_relevance = lambda q, c: [0.5, 0.5]  # type: ignore[method-assign]

    candidates = [
        {"chunk_id": "a", "doc_id": "PMC222", "source_title": "old", "text": "x"},
        {"chunk_id": "b", "doc_id": "PMC111", "source_title": "new", "text": "x"},
    ]
    out = reranker.rerank("papers after 2015", candidates, top_k=2, query_info=Q())
    assert out[0]["doc_id"] == "PMC111"
    assert out[0]["rerank_explain"]["year_hint"] == 2015
