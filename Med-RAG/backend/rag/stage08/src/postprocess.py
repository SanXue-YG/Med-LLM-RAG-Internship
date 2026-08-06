"""阶段 4：答案后处理与来源格式化。"""

from __future__ import annotations

import re
from typing import Any

MEDICAL_DISCLAIMER = (
    "Medical disclaimer: This response is for informational purposes only and "
    "is not a substitute for professional medical advice."
)


def format_sources(chunks: list[Any]) -> list[dict[str, Any]]:
    """将 chunks 规范为 sources 列表。"""
    sources: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        item = _chunk_to_dict(chunk)
        meta = item.get("metadata", {}) or {}
        sources.append(
            {
                "index": idx,
                "chunk_id": item.get("chunk_id") or meta.get("chunk_id"),
                "source_title": meta.get("source_title") or "unknown_source",
                "doc_id": meta.get("doc_id"),
                "relevance_score": _as_float(item.get("relevance_score")),
            }
        )
    return sources


def postprocess_answer(
    answer: str,
    sources: list[dict[str, Any]],
    *,
    add_disclaimer: bool = True,
) -> str:
    """答案后处理：补引用、附来源清单、加免责声明。"""
    text = (answer or "").strip()
    if not text:
        text = "Insufficient evidence to provide a grounded answer."

    refs = _build_reference_markers(sources)
    if refs and not re.search(r"\[\d+\]", text):
        text = f"{text}\n\nEvidence refs: {refs}"

    sources_block = _render_sources_block(sources)
    if sources_block:
        text = f"{text}\n\n{sources_block}"

    if add_disclaimer:
        text = f"{text}\n\n{MEDICAL_DISCLAIMER}"

    return text


def _render_sources_block(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return ""
    lines = ["Sources:"]
    for src in sources:
        idx = src.get("index")
        title = src.get("source_title") or "unknown_source"
        doc_id = src.get("doc_id") or "unknown_doc"
        chunk_id = src.get("chunk_id") or "unknown_chunk"
        score = src.get("relevance_score")
        score_str = f"{score:.4f}" if isinstance(score, float) else "n/a"
        lines.append(f"[{idx}] {title} (doc_id={doc_id}, chunk_id={chunk_id}, score={score_str})")
    return "\n".join(lines)


def _build_reference_markers(sources: list[dict[str, Any]], *, max_refs: int = 5) -> str:
    if not sources:
        return ""
    upper = min(len(sources), max_refs)
    return " ".join(f"[{i}]" for i in range(1, upper + 1))


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _chunk_to_dict(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, dict):
        return chunk
    if hasattr(chunk, "to_dict"):
        return chunk.to_dict()
    return {
        "chunk_id": getattr(chunk, "chunk_id", ""),
        "relevance_score": getattr(chunk, "relevance_score", 0.0),
        "metadata": getattr(chunk, "metadata", {}),
        "text": getattr(chunk, "text", ""),
    }
