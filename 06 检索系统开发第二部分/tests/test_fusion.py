import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from fusion import fuse, fuse_rrf, fuse_simple, fuse_weighted  # noqa: E402


def _hit(cid: str, score: float, rank: int, source: str) -> dict:
    return {
        "chunk_id": cid,
        "doc_id": cid.split("_")[0],
        "source_title": f"title-{cid}",
        "text": f"text-{cid}",
        "source": source,
        "score": score,
        "rank": rank,
    }


def test_simple_merge_dedup():
    v = [_hit("A", 0.9, 1, "vector"), _hit("B", 0.8, 2, "vector")]
    k = [_hit("B", 5.0, 1, "bm25"), _hit("C", 4.0, 2, "bm25")]
    out = fuse_simple(v, k, top_k=10)
    assert [h["chunk_id"] for h in out] == ["A", "B", "C"]
    assert out[1]["vector_rank"] == 2
    assert out[1]["bm25_rank"] is None


def test_rrf_prefers_dual_path():
    v = [_hit("A", 0.9, 1, "vector"), _hit("B", 0.5, 5, "vector")]
    k = [_hit("A", 3.0, 2, "bm25"), _hit("B", 8.0, 1, "bm25")]
    out = fuse_rrf(v, k, top_k=3)
    assert out[0]["chunk_id"] == "A"
    assert out[0]["fusion_score"] > 0
    assert out[0]["vector_rank"] == 1
    assert out[0]["bm25_rank"] == 2


def test_weighted_vector_bias():
    v = [_hit("A", 0.99, 1, "vector"), _hit("B", 0.1, 2, "vector")]
    k = [_hit("B", 100.0, 1, "bm25"), _hit("A", 1.0, 2, "bm25")]
    out = fuse_weighted(v, k, top_k=2, vector_weight=0.8, keyword_weight=0.2)
    assert out[0]["chunk_id"] == "A"


def test_fuse_dispatch():
    v = [_hit("A", 0.9, 1, "vector")]
    k = [_hit("B", 3.0, 1, "bm25")]
    for strategy in ("simple", "rrf", "weighted"):
        out = fuse(v, k, strategy=strategy, top_k=5)
        assert len(out) == 2
        assert out[0]["fusion_strategy"] == strategy
