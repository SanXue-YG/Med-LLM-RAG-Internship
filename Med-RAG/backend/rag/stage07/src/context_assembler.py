"""上下文组装器：去重、多样化、控长截断，产出 LLM 可用 context。"""

from __future__ import annotations

import re
from typing import Any, Iterable

try:
    from .models import (
        AssembledContext,
        ContextMetadata,
        DocumentChunk,
        coerce_to_document_chunks,
    )
except ImportError:
    from models import (  # type: ignore[no-redef]
        AssembledContext,
        ContextMetadata,
        DocumentChunk,
        coerce_to_document_chunks,
    )

# 与 06 BM25 分词风格一致的轻量 token（用于 Jaccard 去重）
_STOPWORDS = frozenset(
    "a an the and or of in on for to with is are was were be been being "
    "what how why when which who".split()
)
_TOKEN_RE = re.compile(r"\b[a-z0-9]+\b", re.IGNORECASE)

DEFAULT_TOKENIZER_NAME = "gpt2"
DEFAULT_DEDUP_THRESHOLD = 0.85
DEFAULT_MAX_PER_SOURCE = 2
DEFAULT_SOURCE_PENALTY = 0.15


def _tokenize_for_jaccard(text: str) -> set[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union


class ContextAssembler:
    """将 06 检索候选组装为受控长度的上下文字符串。"""

    def __init__(
        self,
        tokenizer_name: str | None = DEFAULT_TOKENIZER_NAME,
        *,
        dedup_threshold: float = DEFAULT_DEDUP_THRESHOLD,
        max_per_source: int = DEFAULT_MAX_PER_SOURCE,
        source_penalty: float = DEFAULT_SOURCE_PENALTY,
        chunk_separator: str = "\n\n",
    ) -> None:
        self.tokenizer_name = tokenizer_name
        self.dedup_threshold = dedup_threshold
        self.max_per_source = max_per_source
        self.source_penalty = source_penalty
        self.chunk_separator = chunk_separator
        self._tokenizer: Any = None

    def _load_tokenizer(self) -> Any:
        if self._tokenizer is not None:
            return self._tokenizer
        if not self.tokenizer_name:
            return None
        try:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                self.tokenizer_name,
                use_fast=True,
            )
        except Exception:
            self._tokenizer = None
        return self._tokenizer

    def estimate_tokens(self, text: str) -> int:
        """估算文本 token 数；优先 tokenizer，失败则字符启发式。"""
        if not text:
            return 0
        tokenizer = self._load_tokenizer()
        if tokenizer is not None:
            try:
                return len(tokenizer.encode(text, add_special_tokens=False))
            except Exception:
                pass
        return max(1, len(text) // 4)

    def dedup_by_jaccard(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """按 Jaccard 相似度去重，保留相关性更高的一条。"""
        ordered = sorted(chunks, key=lambda c: c.relevance_score, reverse=True)
        unique: list[DocumentChunk] = []
        token_cache: list[set[str]] = []

        for chunk in ordered:
            tokens = _tokenize_for_jaccard(chunk.text)
            is_duplicate = any(
                _jaccard_similarity(tokens, seen) >= self.dedup_threshold
                for seen in token_cache
            )
            if not is_duplicate:
                unique.append(chunk)
                token_cache.append(tokens)

        return unique

    def _source_key(self, chunk: DocumentChunk) -> str:
        meta = chunk.metadata
        doc_id = meta.get("doc_id")
        if doc_id is not None and str(doc_id).strip():
            return str(doc_id)
        if chunk.source.strip():
            return chunk.source
        return chunk.chunk_id

    def _order_with_diversity(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """在相关性优先前提下，对同源过多的候选降权排序。"""
        remaining = sorted(chunks, key=lambda c: c.relevance_score, reverse=True)
        ordered: list[DocumentChunk] = []
        source_counts: dict[str, int] = {}

        while remaining:
            best_index = 0
            best_score = float("-inf")
            for index, chunk in enumerate(remaining):
                source = self._source_key(chunk)
                count = source_counts.get(source, 0)
                penalty = 0.0
                if count >= self.max_per_source:
                    excess = count - self.max_per_source + 1
                    penalty = excess * self.source_penalty
                effective = chunk.relevance_score - penalty
                if effective > best_score:
                    best_score = effective
                    best_index = index
            picked = remaining.pop(best_index)
            source = self._source_key(picked)
            source_counts[source] = source_counts.get(source, 0) + 1
            ordered.append(picked)

        return ordered

    def _truncate_at_sentence_boundary(self, text: str) -> str:
        """在末 10% 区间内寻找句号边界截断。"""
        if not text:
            return text
        search_start = int(len(text) * 0.9)
        boundary = -1
        for index, char in enumerate(text[search_start:], start=search_start):
            if char in ".!?":
                boundary = index + 1
        if boundary > 0:
            return text[:boundary].rstrip()
        return text.rstrip()

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        if self.estimate_tokens(text) <= max_tokens:
            return text

        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if self.estimate_tokens(text[:mid]) <= max_tokens:
                low = mid
            else:
                high = mid - 1

        return self._truncate_at_sentence_boundary(text[:low])

    def _build_context(
        self,
        chunks: list[DocumentChunk],
        max_context_tokens: int,
    ) -> tuple[str, list[DocumentChunk]]:
        parts: list[str] = []
        selected: list[DocumentChunk] = []
        used_tokens = 0

        for index, chunk in enumerate(chunks):
            separator = self.chunk_separator if index > 0 else ""
            separator_tokens = self.estimate_tokens(separator) if separator else 0
            text_tokens = self.estimate_tokens(chunk.text)
            total_needed = separator_tokens + text_tokens

            if used_tokens + total_needed <= max_context_tokens:
                parts.append(f"{separator}{chunk.text}" if separator else chunk.text)
                selected.append(chunk)
                used_tokens += total_needed
                continue

            remaining = max_context_tokens - used_tokens - separator_tokens
            if remaining <= 0:
                break

            truncated = self._truncate_to_tokens(chunk.text, remaining)
            if truncated.strip():
                parts.append(f"{separator}{truncated}" if separator else truncated)
                selected.append(chunk)
            break

        return "".join(parts), selected

    def _analyze_sources(self, chunks: list[DocumentChunk]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for chunk in chunks:
            key = self._source_key(chunk)
            counts[key] = counts.get(key, 0) + 1
        return {
            "counts": counts,
            "unique_sources": len(counts),
        }

    def assemble(
        self,
        retrieved_docs: Iterable[dict[str, Any] | DocumentChunk],
        *,
        max_context_tokens: int = 2048,
    ) -> AssembledContext:
        """组装上下文：转换 → 去重 → 多样化排序 → 控长拼接。"""
        chunks, skipped = coerce_to_document_chunks(retrieved_docs)
        total_retrieved = len(chunks)

        unique_chunks = self.dedup_by_jaccard(chunks)
        ordered_chunks = self._order_with_diversity(unique_chunks)
        context_text, selected_chunks = self._build_context(
            ordered_chunks,
            max_context_tokens,
        )

        metadata = ContextMetadata(
            total_chunks_retrieved=total_retrieved,
            unique_chunks_after_dedup=len(unique_chunks),
            chunks_selected=len(selected_chunks),
            estimated_tokens=self.estimate_tokens(context_text),
            chunk_sources=self._analyze_sources(selected_chunks),
            skipped_invalid=skipped,
        )

        return AssembledContext(
            context_text=context_text,
            metadata=metadata,
            selected_chunks=selected_chunks,
        )

    def assemble_dict(
        self,
        retrieved_docs: Iterable[dict[str, Any] | DocumentChunk],
        *,
        max_context_tokens: int = 2048,
    ) -> dict[str, Any]:
        """与任务书一致的 dict 返回格式。"""
        return self.assemble(
            retrieved_docs,
            max_context_tokens=max_context_tokens,
        ).to_dict()
