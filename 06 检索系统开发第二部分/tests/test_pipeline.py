import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from pipeline import (  # noqa: E402
    RetrievalPipeline,
    _ensure_enhanced,
    build_eval_report,
)


@dataclass
class _FakeFilter:
    key: str
    value: Any
    executable: bool = False


@dataclass
class _FakeEnhanced:
    original: str
    cleaned: str = ""
    vector_query: str = ""
    keyword_query: str = ""
    filters: list[_FakeFilter] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "vector_query": self.vector_query,
            "keyword_query": self.keyword_query,
            "filters": [{"key": f.key, "value": f.value} for f in self.filters],
        }

    def chroma_where(self) -> dict[str, Any] | None:
        return None


class _FakeEnhancer:
    def process(self, query: str) -> _FakeEnhanced:
        return _FakeEnhanced(
            original=query,
            cleaned=query,
            vector_query=query,
            keyword_query=query.lower(),
        )


class _FakeRetriever:
    def retrieve(self, eq, **kwargs):
        return {
            "query": eq.original,
            "vector_query": eq.vector_query,
            "keyword_query": eq.keyword_query,
            "fusion_strategy": kwargs.get("fusion_strategy", "rrf"),
            "vector_hits": [{"chunk_id": "v1", "doc_id": "PMC1", "text": "a", "source": "vector", "rank": 1}],
            "keyword_hits": [{"chunk_id": "k1", "doc_id": "PMC2", "text": "b", "source": "bm25", "rank": 1}],
            "fused": [
                {"chunk_id": "v1", "doc_id": "PMC1", "text": "a", "source": "fused", "rank": 1},
                {"chunk_id": "k1", "doc_id": "PMC2", "text": "b", "source": "fused", "rank": 2},
            ],
        }


class _FakeReranker:
    def rerank(self, query, candidates, top_k=10, criteria_weights=None, query_info=None):
        out = []
        for i, c in enumerate(reversed(candidates[:top_k]), start=1):
            row = dict(c)
            row.update({"rank": i, "final_score": 1.0 / i, "relevance_score": 0.5})
            out.append(row)
        return out


def test_ensure_enhanced_accepts_string_and_object():
    enhancer = _FakeEnhancer()
    eq = _ensure_enhanced("malaria", enhancer)
    assert eq.original == "malaria"
    same = _ensure_enhanced(eq, enhancer)
    assert same is eq


def test_pipeline_run_end_to_end():
    pipe = RetrievalPipeline(
        _FakeEnhancer(),
        _FakeRetriever(),  # type: ignore[arg-type]
        _FakeReranker(),  # type: ignore[arg-type]
        top_k_fused=5,
        top_k_final=2,
    )
    result = pipe.run("malaria vaccine")
    assert result["query"] == "malaria vaccine"
    assert "enhanced" in result and "retrieval" in result
    assert len(result["reranked"]) == 2
    assert result["reranked"][0]["chunk_id"] == "k1"
    assert "enhance_ms" in result["latency_ms"]
    assert "total_ms" in result["latency_ms"]


def test_pipeline_skip_rerank():
    pipe = RetrievalPipeline(
        _FakeEnhancer(),
        _FakeRetriever(),  # type: ignore[arg-type]
        reranker=None,
        skip_rerank=True,
        top_k_final=1,
    )
    result = pipe.run("test")
    assert len(result["reranked"]) == 1
    assert "rerank_ms" not in result["latency_ms"]


def test_build_eval_report():
    results = [
        {
            "query": "q1",
            "latency_ms": {"total_ms": 100.0},
            "reranked": [{"chunk_id": "c1"}],
        },
        {
            "query": "q2",
            "latency_ms": {"total_ms": 200.0},
            "reranked": [{"chunk_id": "c2"}],
        },
    ]
    report = build_eval_report(
        results,
        mode="sample",
        fusion_strategy="rrf",
        top_k_final=5,
        skip_rerank=False,
    )
    assert report["query_count"] == 2
    assert report["summary"]["top1_chunk_ids"][0]["chunk_id"] == "c1"
    assert report["summary"]["latency_ms"]["total_p50"] == 150.0
    assert report["summary"]["latency_ms"]["total_p95"] == 200.0
