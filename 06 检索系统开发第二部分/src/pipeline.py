"""端到端检索流水线：enhance → multipath retrieve → fusion → rerank。"""

from __future__ import annotations

import sys
import time
from typing import Any

try:
    from .config import (
        DEFAULT_FUSION_STRATEGY,
        Mode,
        resolve_slim_path,
        stage05_src,
    )
    from .fusion import FusionStrategy
    from .multipath_retriever import MultiPathRetriever
    from .reranker import DEFAULT_CRITERIA_WEIGHTS, Reranker
    from .rerank_features import SlimMetadataLookup
except ImportError:
    from config import (  # type: ignore[no-redef]
        DEFAULT_FUSION_STRATEGY,
        Mode,
        resolve_slim_path,
        stage05_src,
    )
    from fusion import FusionStrategy  # type: ignore[no-redef]
    from multipath_retriever import MultiPathRetriever  # type: ignore[no-redef]
    from reranker import DEFAULT_CRITERIA_WEIGHTS, Reranker  # type: ignore[no-redef]
    from rerank_features import SlimMetadataLookup  # type: ignore[no-redef]

DEFAULT_DEMO_QUERIES: list[str] = [
    "metformin cardiovascular effects",
    "papers on malaria after 2015",
    "MI treatment guideline",
    "circadian rhythm sliding window chunks",
    "warfarin atrial fibrillation elderly",
]


def _load_enhancer(synonyms_path: str | None = None) -> Any:
    s05 = stage05_src()
    if str(s05) not in sys.path:
        sys.path.insert(0, str(s05))
    from query_enhancer import MedicalQueryEnhancer  # noqa: WPS433

    if synonyms_path is None:
        return MedicalQueryEnhancer()
    return MedicalQueryEnhancer(synonyms_path)


def _ensure_enhanced(query: str | Any, enhancer: Any) -> Any:
    if hasattr(query, "vector_query") and hasattr(query, "keyword_query"):
        return query
    return enhancer.process(str(query))


class RetrievalPipeline:
    """05 查询增强 + 多路召回融合 + 多准则重排。"""

    def __init__(
        self,
        enhancer: Any,
        retriever: MultiPathRetriever,
        reranker: Reranker | None = None,
        *,
        mode: Mode = "sample",
        fusion_strategy: FusionStrategy | str = DEFAULT_FUSION_STRATEGY,
        top_k_vector: int = 20,
        top_k_keyword: int = 20,
        top_k_fused: int = 30,
        top_k_final: int = 10,
        criteria_weights: dict[str, float] | None = None,
        skip_rerank: bool = False,
    ) -> None:
        self.enhancer = enhancer
        self.retriever = retriever
        self.reranker = reranker
        self.mode = mode
        self.fusion_strategy = fusion_strategy
        self.top_k_vector = top_k_vector
        self.top_k_keyword = top_k_keyword
        self.top_k_fused = top_k_fused
        self.top_k_final = top_k_final
        self.criteria_weights = criteria_weights or DEFAULT_CRITERIA_WEIGHTS
        self.skip_rerank = skip_rerank

    @classmethod
    def from_mode(
        cls,
        mode: Mode = "sample",
        *,
        fusion_strategy: FusionStrategy | str = DEFAULT_FUSION_STRATEGY,
        top_k_vector: int = 20,
        top_k_keyword: int = 20,
        top_k_fused: int = 30,
        top_k_final: int = 10,
        criteria_weights: dict[str, float] | None = None,
        skip_rerank: bool = False,
        load_reranker: bool = True,
        synonyms_path: str | None = None,
    ) -> RetrievalPipeline:
        """按 config 挂载 05 enhancer + 04/06 retriever + reranker。"""
        enhancer = _load_enhancer(synonyms_path)
        retriever = MultiPathRetriever.from_mode(mode)
        reranker = None
        if load_reranker and not skip_rerank:
            lookup = SlimMetadataLookup(resolve_slim_path())
            reranker = Reranker(metadata_lookup=lookup)
        return cls(
            enhancer,
            retriever,
            reranker,
            mode=mode,
            fusion_strategy=fusion_strategy,
            top_k_vector=top_k_vector,
            top_k_keyword=top_k_keyword,
            top_k_fused=top_k_fused,
            top_k_final=top_k_final,
            criteria_weights=criteria_weights,
            skip_rerank=skip_rerank,
        )

    def run(self, query: str | Any, *, skip_rerank: bool | None = None) -> dict[str, Any]:
        """单条 query 端到端检索。"""
        do_rerank = not (skip_rerank if skip_rerank is not None else self.skip_rerank)
        latency: dict[str, float] = {}

        t0 = time.perf_counter()
        eq = _ensure_enhanced(query, self.enhancer)
        latency["enhance_ms"] = round((time.perf_counter() - t0) * 1000, 2)

        t1 = time.perf_counter()
        retrieval = self.retriever.retrieve(
            eq,
            top_k_vector=self.top_k_vector,
            top_k_keyword=self.top_k_keyword,
            fusion_strategy=self.fusion_strategy,
            top_k_fused=self.top_k_fused,
        )
        latency["retrieve_ms"] = round((time.perf_counter() - t1) * 1000, 2)

        reranked: list[dict[str, Any]] = []
        if do_rerank:
            if self.reranker is None:
                lookup = SlimMetadataLookup(resolve_slim_path())
                self.reranker = Reranker(metadata_lookup=lookup)
            t2 = time.perf_counter()
            reranked = self.reranker.rerank(
                eq.vector_query,
                retrieval["fused"],
                top_k=self.top_k_final,
                criteria_weights=self.criteria_weights,
                query_info=eq,
            )
            latency["rerank_ms"] = round((time.perf_counter() - t2) * 1000, 2)
        else:
            reranked = retrieval["fused"][: self.top_k_final]

        latency["total_ms"] = round(sum(latency.values()), 2)

        enhanced_dict = eq.to_dict() if hasattr(eq, "to_dict") else {"original": str(query)}

        return {
            "query": eq.original if hasattr(eq, "original") else str(query),
            "enhanced": enhanced_dict,
            "fusion_strategy": self.fusion_strategy,
            "retrieval": {
                "vector_hits": retrieval["vector_hits"],
                "keyword_hits": retrieval["keyword_hits"],
                "fused": retrieval["fused"],
            },
            "reranked": reranked,
            "latency_ms": latency,
        }

    def run_batch(self, queries: list[str], **run_kwargs: Any) -> list[dict[str, Any]]:
        return [self.run(q, **run_kwargs) for q in queries]


def build_eval_report(
    results: list[dict[str, Any]],
    *,
    mode: Mode,
    fusion_strategy: str,
    top_k_final: int,
    skip_rerank: bool,
) -> dict[str, Any]:
    """组装 CLI / notebook 导出的评测 JSON。"""
    return {
        "mode": mode,
        "fusion_strategy": fusion_strategy,
        "skip_rerank": skip_rerank,
        "top_k_final": top_k_final,
        "query_count": len(results),
        "queries": results,
        "summary": {
            "latency_ms": {
                "total_p50": _percentile([r["latency_ms"]["total_ms"] for r in results], 50),
                "total_p95": _percentile([r["latency_ms"]["total_ms"] for r in results], 95),
            },
            "top1_chunk_ids": [
                {
                    "query": r["query"],
                    "chunk_id": r["reranked"][0]["chunk_id"] if r["reranked"] else None,
                }
                for r in results
            ],
        },
    }


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if pct == 50:
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return round(ordered[mid], 2)
        return round((ordered[mid - 1] + ordered[mid]) / 2, 2)
    idx = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * pct / 100))))
    return round(ordered[idx], 2)
