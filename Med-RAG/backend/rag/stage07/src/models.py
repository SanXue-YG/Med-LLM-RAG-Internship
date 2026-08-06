"""07 生成模块与提示词工程第一部分 — 数据结构。

DocumentChunk：单条候选文档块（任务书定义）。
AssembledContext：ContextAssembler 组装结果（阶段 2 产出，阶段 1 先定义契约）。

06 候选 dict → DocumentChunk 映射规则见 ../输入候选格式约定.md §3。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

# 相关性分瀑布回退（reranked → fused → 原始 hit）
_RELEVANCE_SCORE_KEYS = ("final_score", "fusion_score", "relevance_score", "score")

# DocumentChunk.source 取值顺序（文献名 / doc_id / 召回通道）
_SOURCE_KEYS = ("source_title", "doc_id", "source")

# chunk_id 回退
_CHUNK_ID_KEYS = ("chunk_id", "doc_id")


@dataclass
class DocumentChunk:
    """检索候选文档块（供上下文组装器消费）。"""

    text: str
    metadata: dict[str, Any]
    relevance_score: float
    source: str
    chunk_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextMetadata:
    """上下文组装过程统计（对应任务书 context_metadata）。"""

    total_chunks_retrieved: int
    unique_chunks_after_dedup: int = 0
    chunks_selected: int = 0
    estimated_tokens: int = 0
    chunk_sources: dict[str, Any] = field(default_factory=dict)
    skipped_invalid: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssembledContext:
    """ContextAssembler.assemble() 的返回结构。"""

    context_text: str
    metadata: ContextMetadata
    selected_chunks: list[DocumentChunk] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_text": self.context_text,
            "metadata": self.metadata.to_dict(),
            "selected_chunks": [c.to_dict() for c in self.selected_chunks],
        }


def _resolve_relevance_score(candidate: dict[str, Any]) -> float:
    for key in _RELEVANCE_SCORE_KEYS:
        value = candidate.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _resolve_source(candidate: dict[str, Any]) -> str:
    for key in _SOURCE_KEYS:
        value = candidate.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return "unknown"


def _resolve_chunk_id(candidate: dict[str, Any], *, index: int) -> str:
    for key in _CHUNK_ID_KEYS:
        value = candidate.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return f"unknown_{index}"


def _build_metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    """候选 dict 中除 text 外的字段整体收纳进 metadata。"""
    return {k: v for k, v in candidate.items() if k != "text"}


def document_chunk_from_candidate(
    candidate: dict[str, Any],
    *,
    index: int = 0,
) -> DocumentChunk | None:
    """将 06 候选 dict 转为 DocumentChunk；text 无效时返回 None。"""
    text = candidate.get("text")
    if not isinstance(text, str) or not text.strip():
        return None

    return DocumentChunk(
        text=text,
        metadata=_build_metadata(candidate),
        relevance_score=_resolve_relevance_score(candidate),
        source=_resolve_source(candidate),
        chunk_id=_resolve_chunk_id(candidate, index=index),
    )


def coerce_to_document_chunks(
    items: Iterable[dict[str, Any] | DocumentChunk],
) -> tuple[list[DocumentChunk], int]:
    """将混合输入（dict / DocumentChunk）统一为 DocumentChunk 列表。

    Returns:
        (chunks, skipped_count) — skipped_count 为 text 无效被跳过的 dict 条数。
    """
    chunks: list[DocumentChunk] = []
    skipped = 0
    dict_index = 0

    for item in items:
        if isinstance(item, DocumentChunk):
            if item.text.strip():
                chunks.append(item)
            else:
                skipped += 1
            continue

        if not isinstance(item, dict):
            skipped += 1
            continue

        converted = document_chunk_from_candidate(item, index=dict_index)
        dict_index += 1
        if converted is None:
            skipped += 1
        else:
            chunks.append(converted)

    return chunks, skipped
