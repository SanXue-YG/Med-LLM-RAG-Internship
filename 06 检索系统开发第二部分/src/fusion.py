"""多路检索结果融合：simple / rrf / weighted。"""

from __future__ import annotations

from typing import Any, Literal

FusionStrategy = Literal["simple", "rrf", "weighted"]

RRF_K = 60
DEFAULT_VECTOR_WEIGHT = 0.6
DEFAULT_KEYWORD_WEIGHT = 0.4

_META_KEYS = (
    "doc_id",
    "source_title",
    "text",
    "chunk_index",
    "total_chunks",
    "token_count",
    "strategy",
)


def _copy_meta(hit: dict[str, Any]) -> dict[str, Any]:
    return {k: hit.get(k) for k in _META_KEYS if k in hit}


def _minmax_norm(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi <= lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def fuse_simple(
    vector_hits: list[dict[str, Any]],
    keyword_hits: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """合并去重：先向量路，再补入 BM25 独有候选（保留分路得分）。"""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    def add(hit: dict[str, Any], path: str) -> None:
        cid = hit["chunk_id"]
        if cid in seen:
            return
        seen.add(cid)
        row = _copy_meta(hit)
        row.update(
            {
                "chunk_id": cid,
                "source": "fused",
                "fusion_strategy": "simple",
                "fusion_score": None,
                "vector_score": hit.get("score") if path == "vector" else None,
                "bm25_score": hit.get("score") if path == "bm25" else None,
                "vector_rank": hit.get("rank") if path == "vector" else None,
                "bm25_rank": hit.get("rank") if path == "bm25" else None,
            }
        )
        merged.append(row)

    for h in vector_hits:
        add(h, "vector")
    for h in keyword_hits:
        add(h, "bm25")

    for i, row in enumerate(merged[:top_k], start=1):
        row["rank"] = i
    return merged[:top_k]


def fuse_rrf(
    vector_hits: list[dict[str, Any]],
    keyword_hits: list[dict[str, Any]],
    top_k: int,
    *,
    k: int = RRF_K,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion：score = Σ 1/(k + rank)。"""
    scores: dict[str, float] = {}
    meta: dict[str, dict[str, Any]] = {}
    path_info: dict[str, dict[str, Any]] = {}

    def accumulate(hits: list[dict[str, Any]], path: str) -> None:
        for hit in hits:
            cid = hit["chunk_id"]
            rank = int(hit.get("rank", 0))
            if rank <= 0:
                continue
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            if cid not in meta:
                meta[cid] = _copy_meta(hit)
            info = path_info.setdefault(cid, {})
            info[f"{path}_score"] = hit.get("score")
            info[f"{path}_rank"] = rank

    accumulate(vector_hits, "vector")
    accumulate(keyword_hits, "bm25")

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    out: list[dict[str, Any]] = []
    for i, (cid, fscore) in enumerate(ranked, start=1):
        info = path_info.get(cid, {})
        row = dict(meta.get(cid, {}))
        row.update(
            {
                "chunk_id": cid,
                "source": "fused",
                "fusion_strategy": "rrf",
                "fusion_score": float(fscore),
                "vector_score": info.get("vector_score"),
                "bm25_score": info.get("bm25_score"),
                "vector_rank": info.get("vector_rank"),
                "bm25_rank": info.get("bm25_rank"),
                "rank": i,
            }
        )
        out.append(row)
    return out


def fuse_weighted(
    vector_hits: list[dict[str, Any]],
    keyword_hits: list[dict[str, Any]],
    top_k: int,
    *,
    vector_weight: float = DEFAULT_VECTOR_WEIGHT,
    keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
) -> list[dict[str, Any]]:
    """分数归一化后加权求和（向量权重更高）。"""
    scores: dict[str, float] = {}
    meta: dict[str, dict[str, Any]] = {}
    path_info: dict[str, dict[str, Any]] = {}

    def accumulate(hits: list[dict[str, Any]], path: str, weight: float) -> None:
        raw = [float(h.get("score", 0.0)) for h in hits]
        normed = _minmax_norm(raw)
        for hit, nscore in zip(hits, normed):
            cid = hit["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + weight * nscore
            if cid not in meta:
                meta[cid] = _copy_meta(hit)
            info = path_info.setdefault(cid, {})
            info[f"{path}_score"] = hit.get("score")
            info[f"{path}_rank"] = hit.get("rank")

    accumulate(vector_hits, "vector", vector_weight)
    accumulate(keyword_hits, "bm25", keyword_weight)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    out: list[dict[str, Any]] = []
    for i, (cid, fscore) in enumerate(ranked, start=1):
        info = path_info.get(cid, {})
        row = dict(meta.get(cid, {}))
        row.update(
            {
                "chunk_id": cid,
                "source": "fused",
                "fusion_strategy": "weighted",
                "fusion_score": float(fscore),
                "vector_score": info.get("vector_score"),
                "bm25_score": info.get("bm25_score"),
                "vector_rank": info.get("vector_rank"),
                "bm25_rank": info.get("bm25_rank"),
                "rank": i,
            }
        )
        out.append(row)
    return out


def fuse(
    vector_hits: list[dict[str, Any]],
    keyword_hits: list[dict[str, Any]],
    strategy: FusionStrategy = "rrf",
    top_k: int = 10,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """统一融合入口。"""
    if strategy == "simple":
        return fuse_simple(vector_hits, keyword_hits, top_k)
    if strategy == "weighted":
        return fuse_weighted(vector_hits, keyword_hits, top_k, **kwargs)
    return fuse_rrf(vector_hits, keyword_hits, top_k, **kwargs)
