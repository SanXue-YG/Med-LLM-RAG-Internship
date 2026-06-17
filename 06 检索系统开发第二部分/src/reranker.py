"""BGE cross-encoder 重排序 + 多准则特征融合。"""

from __future__ import annotations

from typing import Any

try:
    from .config import RERANK_MODEL
    from .rerank_features import (
        SlimMetadataLookup,
        authority_score,
        combine_criteria_scores,
        extract_year_hint,
        recency_score,
    )
except ImportError:
    from config import RERANK_MODEL  # type: ignore[no-redef]
    from rerank_features import (  # type: ignore[no-redef]
        SlimMetadataLookup,
        authority_score,
        combine_criteria_scores,
        extract_year_hint,
        recency_score,
    )

DEFAULT_CRITERIA_WEIGHTS: dict[str, float] = {
    "relevance": 0.6,
    "recency": 0.25,
    "authority": 0.15,
}

MAX_DOC_CHARS = 1500


class Reranker:
    """bge-reranker-base cross-encoder + recency/authority 多准则重排。"""

    def __init__(
        self,
        model_name: str = RERANK_MODEL,
        device: str | None = None,
        batch_size: int = 8,
        metadata_lookup: SlimMetadataLookup | None = None,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.metadata_lookup = metadata_lookup or SlimMetadataLookup()
        self._tokenizer = None
        self._model = None
        self._device = device

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        print(f"[Reranker] 加载 {self.model_name}（首次运行需下载 ~1.1GB，请耐心等待）...")
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        if self._device is None:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model.to(self._device)
        self._model.eval()
        print(f"[Reranker] 就绪，device={self._device}")

    def score_relevance(self, query: str, candidates: list[dict[str, Any]]) -> list[float]:
        """query-doc 对 cross-encoder 打分 → sigmoid 概率。"""
        if not candidates:
            return []
        self._ensure_model()
        import torch

        pairs = [[query, _doc_text(c)] for c in candidates]
        scores: list[float] = []
        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i : i + self.batch_size]
            inputs = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to(self._device)
            with torch.no_grad():
                logits = self._model(**inputs, return_dict=True).logits.view(-1)
                probs = torch.sigmoid(logits).cpu().tolist()
            scores.extend(float(p) for p in probs)
        return scores

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = 10,
        criteria_weights: dict[str, float] | None = None,
        query_info: Any | None = None,
    ) -> list[dict[str, Any]]:
        """多准则重排，返回 top_k 及解释字段。"""
        if not candidates:
            return []

        weights = criteria_weights or DEFAULT_CRITERIA_WEIGHTS
        year_hint = extract_year_hint(query_info) if query_info is not None else None

        doc_ids = {c.get("doc_id") for c in candidates if c.get("doc_id")}
        self.metadata_lookup.preload({d for d in doc_ids if d})

        relevance_scores = self.score_relevance(query, candidates)

        scored: list[dict[str, Any]] = []
        for cand, rel in zip(candidates, relevance_scores):
            meta = self.metadata_lookup.get(cand.get("doc_id")) or {}
            pub_year = meta.get("pub_year")
            journal = meta.get("journal")
            rec = recency_score(pub_year, year_gte=year_hint)
            auth = authority_score(journal)
            final = combine_criteria_scores(rel, rec, auth, weights)

            row = dict(cand)
            row.update(
                {
                    "relevance_score": round(rel, 6),
                    "recency_score": round(rec, 6),
                    "authority_score": round(auth, 6),
                    "final_score": round(final, 6),
                    "pub_year": pub_year,
                    "journal": journal,
                    "criteria_weights": dict(weights),
                    "rerank_explain": {
                        "relevance": rel,
                        "recency": rec,
                        "authority": auth,
                        "year_hint": year_hint,
                        "weighted_sum": final,
                    },
                }
            )
            scored.append(row)

        scored.sort(key=lambda x: x["final_score"], reverse=True)
        for i, row in enumerate(scored[:top_k], start=1):
            row["rank"] = i
        return scored[:top_k]


def _doc_text(candidate: dict[str, Any]) -> str:
    title = candidate.get("source_title") or ""
    body = candidate.get("text") or ""
    combined = f"{title}\n\n{body}".strip()
    return combined[:MAX_DOC_CHARS]
