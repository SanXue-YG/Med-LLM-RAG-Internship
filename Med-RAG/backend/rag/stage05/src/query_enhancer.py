"""
05 检索系统开发第一部分 — 查询理解与增强。

嵌入模型与 04 建库一致：BAAI/bge-small-en-v1.5。
vector_query 为 raw 文本；BGE 指令前缀由 04 DocumentEmbedder.encode_queries() 添加。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from medical_patterns import extract_entities
from models import EnhancedQuery, EntityMatch, FilterItem

# 轻量英文停用词（关键词查询用）
_STOPWORDS = frozenset(
    "a an the and or of in on for to with is are was were be been being "
    "what how why when which who".split()
)

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


class MedicalQueryEnhancer:
    """医学查询清洗、实体识别、同义词扩展与 filter 解析。"""

    def __init__(self, synonyms_path: str | Path | None = None):
        if synonyms_path is None:
            synonyms_path = Path(__file__).resolve().parents[1] / "data" / "medical_synonyms.json"
        self.synonyms_path = Path(synonyms_path)
        with open(self.synonyms_path, encoding="utf-8") as f:
            data = json.load(f)
        self._abbrev: dict[str, list[str]] = {
            k.lower(): v for k, v in data.get("abbreviations", {}).items()
        }
        self._terms: dict[str, list[str]] = {
            k.lower(): v for k, v in data.get("terms", {}).items()
        }

    def process(self, query: str) -> EnhancedQuery:
        original = query
        cleaned = self._clean(query)
        meta: dict[str, Any] = {
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "language": "en",
        }

        if _CJK_RE.search(cleaned):
            meta["language"] = "zh_detected"
            meta["note"] = "Chinese detected; English-first per schedule. Translation not applied."

        entities = extract_entities(cleaned)
        expanded = self._expand_synonyms(cleaned, entities)
        filters = self._extract_filters(cleaned)
        keyword_query = self._build_keyword_query(cleaned, entities, expanded)

        return EnhancedQuery(
            original=original,
            cleaned=cleaned,
            entities=entities,
            expanded_terms=expanded,
            vector_query=cleaned,
            keyword_query=keyword_query,
            filters=filters,
            metadata=meta,
        )

    @staticmethod
    def _clean(query: str) -> str:
        text = query.strip()
        text = re.sub(r"\s+", " ", text)
        return text

    def _expand_synonyms(self, text: str, entities: list[EntityMatch]) -> list[str]:
        expanded: list[str] = []
        seen: set[str] = set()
        lower = text.lower()

        def add(term: str) -> None:
            t = term.strip().lower()
            if t and t not in seen:
                seen.add(t)
                expanded.append(term.strip())

        # 整句术语表
        for key, alts in self._terms.items():
            if key in lower:
                for a in alts:
                    add(a)

        # 实体 + 缩写白名单
        tokens = re.findall(r"\b[a-z0-9]+\b", lower)
        for tok in tokens:
            if tok in self._abbrev:
                for a in self._abbrev[tok]:
                    add(a)
            for ent in entities:
                if ent.text.lower() == tok and tok in self._terms:
                    for a in self._terms[tok]:
                        add(a)

        return expanded

    def _build_keyword_query(
        self,
        cleaned: str,
        entities: list[EntityMatch],
        expanded: list[str],
    ) -> str:
        tokens = re.findall(r"\b[a-z0-9]+\b", cleaned.lower())
        core = [t for t in tokens if t not in _STOPWORDS]
        parts = list(core)
        for e in entities:
            parts.append(e.text.lower())
        parts.extend(w.lower() for w in expanded)
        # 去重保序
        seen: set[str] = set()
        out: list[str] = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                out.append(p)
        return " ".join(out)

    def _extract_filters(self, text: str) -> list[FilterItem]:
        """解析 filter；仅 strategy/doc_id 等可在当前 Chroma metadata 执行。"""
        items: list[FilterItem] = []
        lower = text.lower()

        # strategy（索引可执行）
        if "sliding window" in lower or "sliding_window" in lower:
            items.append(
                FilterItem(
                    key="strategy",
                    value="sliding_window",
                    executable=True,
                    note="Chroma metadata 支持",
                )
            )
        if re.search(r"\bsingle\s+chunk\b", lower) or "single block" in lower:
            items.append(
                FilterItem(
                    key="strategy",
                    value="single",
                    executable=True,
                    note="Chroma metadata 支持",
                )
            )

        # 年份（解析但不执行）
        m = re.search(r"\b(?:after|since|from)\s+(20\d{2})\b", lower)
        if m:
            items.append(
                FilterItem(
                    key="year_gte",
                    value=int(m.group(1)),
                    executable=False,
                    note="索引无 pub_year；RAG 阶段检索后过滤",
                )
            )
        m = re.search(r"\b(20\d{2})\s*[-–]\s*(20\d{2})\b", lower)
        if m:
            items.append(
                FilterItem(
                    key="year_gte",
                    value=int(m.group(1)),
                    executable=False,
                )
            )
            items.append(
                FilterItem(
                    key="year_lte",
                    value=int(m.group(2)),
                    executable=False,
                    note="索引无 pub_year",
                )
            )
        if re.search(r"\b(?:last|recent|past)\s+(\d+)\s+years?\b", lower):
            items.append(
                FilterItem(
                    key="year_relative_years",
                    value=int(re.search(r"\b(?:last|recent|past)\s+(\d+)\s+years?\b", lower).group(1)),
                    executable=False,
                    note="需结合当前年与 slim JSONL 后过滤",
                )
            )

        # journal（解析但不执行）
        m = re.search(r"\b(?:in|from)\s+(nature|lancet|nejm|bmj|plos)\b", lower)
        if m:
            items.append(
                FilterItem(
                    key="journal_hint",
                    value=m.group(1),
                    executable=False,
                    note="索引无 journal 字段",
                )
            )

        return items
