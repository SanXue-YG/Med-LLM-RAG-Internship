"""重排序特征：recency / authority（回查 slim JSONL）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from .config import resolve_slim_path
except ImportError:
    from config import resolve_slim_path  # type: ignore[no-redef]

# 期刊权威性规则表（小写匹配子串）
JOURNAL_AUTHORITY: dict[str, float] = {
    "nature": 1.0,
    "lancet": 1.0,
    "new england journal of medicine": 1.0,
    "nejm": 1.0,
    "bmj": 0.9,
    "jama": 0.9,
    "plos medicine": 0.85,
    "plos one": 0.7,
    "scientific reports": 0.75,
    "cell": 0.95,
    "science": 0.95,
}

DEFAULT_AUTHORITY = 0.5
RECENCY_BASE_YEAR = 1990


class SlimMetadataLookup:
    """按 doc_id（= pmcid）从 slim JSONL 回查 pub_year / journal。"""

    def __init__(self, slim_path: str | Path | None = None) -> None:
        self.slim_path = Path(slim_path or resolve_slim_path())
        self._cache: dict[str, dict[str, Any]] = {}

    def preload(self, doc_ids: set[str]) -> int:
        """单次顺序扫描 slim，加载指定 doc_ids 的元数据。"""
        missing = {d for d in doc_ids if d and d not in self._cache}
        if not missing or not self.slim_path.is_file():
            return 0

        loaded = 0
        with open(self.slim_path, encoding="utf-8") as f:
            for line in f:
                if not missing:
                    break
                row = json.loads(line)
                pmcid = row.get("pmcid")
                if pmcid in missing:
                    self._cache[pmcid] = {
                        "pmcid": pmcid,
                        "pub_year": _parse_year(row.get("pub_year")),
                        "journal": row.get("journal") or "",
                    }
                    missing.remove(pmcid)
                    loaded += 1
        return loaded

    def get(self, doc_id: str | None) -> dict[str, Any] | None:
        if not doc_id:
            return None
        return self._cache.get(doc_id)

    def cached_count(self) -> int:
        return len(self._cache)


def _parse_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    m = re.search(r"(20\d{2}|19\d{2})", str(value))
    return int(m.group(1)) if m else None


def recency_score(
    pub_year: int | None,
    *,
    current_year: int = 2026,
    base_year: int = RECENCY_BASE_YEAR,
    year_gte: int | None = None,
) -> float:
    """时效性分：pub_year 线性映射到 [0,1]；若指定 year_gte 则更早的文献降权。"""
    if pub_year is None:
        return 0.5
    span = max(current_year - base_year, 1)
    score = max(0.0, min(1.0, (pub_year - base_year) / span))
    if year_gte is not None and pub_year < year_gte:
        penalty = (year_gte - pub_year) / span
        score = max(0.0, score - penalty)
    return score


def authority_score(journal: str | None) -> float:
    """期刊权威性分：规则表子串匹配，未知期刊返回默认分。"""
    if not journal:
        return DEFAULT_AUTHORITY
    lower = journal.lower()
    best = DEFAULT_AUTHORITY
    for key, weight in JOURNAL_AUTHORITY.items():
        if key in lower:
            best = max(best, weight)
    return best


def extract_year_hint(query_info: Any) -> int | None:
    """从 05 EnhancedQuery.filters 提取 year_gte。"""
    filters = getattr(query_info, "filters", None)
    if not filters:
        return None
    for f in filters:
        key = getattr(f, "key", None) if not isinstance(f, dict) else f.get("key")
        if key == "year_gte":
            val = getattr(f, "value", None) if not isinstance(f, dict) else f.get("value")
            if isinstance(val, int):
                return val
    return None


def combine_criteria_scores(
    relevance: float,
    recency: float,
    authority: float,
    weights: dict[str, float],
) -> float:
    """加权合成最终分。"""
    w_rel = weights.get("relevance", 0.6)
    w_rec = weights.get("recency", 0.25)
    w_auth = weights.get("authority", 0.15)
    total_w = w_rel + w_rec + w_auth
    if total_w <= 0:
        return relevance
    return (w_rel * relevance + w_rec * recency + w_auth * authority) / total_w
