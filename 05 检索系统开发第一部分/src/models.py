"""05 检索系统开发第一部分 — 查询增强数据结构。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EntityMatch:
    """医学实体识别结果。"""

    type: str
    text: str
    start: int
    end: int


@dataclass
class FilterItem:
    """从 query 解析出的过滤条件。"""

    key: str
    value: Any
    executable: bool
    note: str = ""


@dataclass
class EnhancedQuery:
    """查询理解与增强的输出（供检索模块消费）。"""

    original: str
    cleaned: str
    entities: list[EntityMatch] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)
    vector_query: str = ""
    keyword_query: str = ""
    filters: list[FilterItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def filters_dict(self) -> dict[str, Any]:
        return {f.key: f.value for f in self.filters}

    def chroma_where(self) -> dict[str, Any] | None:
        """当前索引可执行的 Chroma where 条件（等值）。"""
        parts = {f.key: f.value for f in self.filters if f.executable}
        if not parts:
            return None
        if len(parts) == 1:
            k, v = next(iter(parts.items()))
            return {k: v}
        return parts

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["filters"] = [asdict(f) for f in self.filters]
        return d
