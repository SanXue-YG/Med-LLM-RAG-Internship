import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from bm25_index import BM25Index  # noqa: E402
from multipath_retriever import MultiPathRetriever, chroma_results_to_hits  # noqa: E402


@dataclass
class _FakeQuery:
    original: str
    vector_query: str
    keyword_query: str

    def chroma_where(self) -> dict[str, Any] | None:
        return None


class _FakeBuilder:
    def query(self, query_text: str, n_results: int = 5, where_filter=None):
        return {
            "ids": [["PMC176545", "PMC193604_chunk1"]],
            "distances": [[0.2, 0.4]],
            "metadatas": [
                [
                    {"doc_id": "PMC176545", "source_title": "malaria", "strategy": "single"},
                    {"doc_id": "PMC193604", "source_title": "circadian", "strategy": "sliding_window"},
                ]
            ],
            "documents": [["malaria text", "circadian text"]],
        }


def test_chroma_results_to_hits():
    hits = chroma_results_to_hits(_FakeBuilder().query("x"))
    assert hits[0]["source"] == "vector"
    assert hits[0]["rank"] == 1
    assert hits[0]["score"] == 0.8


def test_multipath_retrieve_structure():
    bm25 = BM25Index()
    bm25.build(mode="sample")
    retriever = MultiPathRetriever(_FakeBuilder(), bm25)
    eq = _FakeQuery("malaria", "malaria vaccine", "malaria plasmodium")
    result = retriever.retrieve(eq, top_k_vector=5, top_k_keyword=5, top_k_fused=5)
    assert "vector_hits" in result and "keyword_hits" in result and "fused" in result
    assert len(result["fused"]) <= 5
    assert result["fused"][0]["fusion_strategy"] == "rrf"
    for key in ("fusion_score", "vector_score", "bm25_score", "rank", "chunk_id"):
        assert key in result["fused"][0] or key == "bm25_score"
