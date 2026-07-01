"""JSON 提取、修复与证据评估解析。"""

from __future__ import annotations

import json
import re
from typing import Any

EVIDENCE_EVAL_FIELDS = ("relevant_chunk_ids", "excluded_chunk_ids", "notes")


def extract_json(text: str) -> dict | None:
    """从模型文本中提取 JSON 对象（剥离围栏；失败时尝试 ``repair_json``）。"""
    if not text or not isinstance(text, str):
        return None

    candidates: list[str] = []
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        candidates.append(fence.group(1).strip())
    candidates.append(text.strip())

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    seen: set[str] = set()
    for candidate in candidates:
        for variant in (candidate, repair_json(candidate)):
            if not variant or variant in seen:
                continue
            seen.add(variant)
            parsed = _try_parse_dict(variant)
            if parsed is not None:
                return parsed
    return None


def repair_json(text: str) -> str:
    """补全常见残缺 JSON（缺失引号 / 括号、尾逗号等）。"""
    if not isinstance(text, str):
        return ""

    s = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()

    start = s.find("{")
    if start == -1:
        return s
    s = s[start:]

    s = re.sub(r",\s*([}\]])", r"\1", s)
    s = _close_open_string(s)
    s = _balance_brackets(s)
    return s


def parse_evidence_evaluation(text: str) -> dict | None:
    """解析证据评估 JSON 并规范为最小 schema。"""
    return normalize_evidence_evaluation(extract_json(text))


def normalize_evidence_evaluation(obj: dict | None) -> dict | None:
    """规范证据评估字段；非 dict 返回 ``None``。"""
    if not isinstance(obj, dict):
        return None
    return {
        "relevant_chunk_ids": _as_str_list(obj.get("relevant_chunk_ids")),
        "excluded_chunk_ids": _as_str_list(obj.get("excluded_chunk_ids")),
        "notes": str(obj.get("notes", "")),
    }


def filter_chunks_by_evidence_eval(
    selected_chunks: list[Any],
    evaluation: dict | None,
) -> list[Any]:
    """按评估结果筛选 chunks；``evaluation`` 为 ``None`` 时**不筛选**（降级）。"""
    if evaluation is None:
        return list(selected_chunks)

    excluded = set(evaluation.get("excluded_chunk_ids") or [])
    relevant = evaluation.get("relevant_chunk_ids") or []

    if relevant:
        rel = set(relevant)
        kept = [c for c in selected_chunks if _chunk_id(c) in rel]
        if kept:
            return kept

    if excluded:
        return [c for c in selected_chunks if _chunk_id(c) not in excluded]

    return list(selected_chunks)


def _try_parse_dict(raw: str) -> dict | None:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v)]
    return [str(value)]


def _chunk_id(chunk: Any) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("chunk_id") or chunk.get("doc_id") or "")
    return str(getattr(chunk, "chunk_id", "") or getattr(chunk, "doc_id", ""))


def _close_open_string(text: str) -> str:
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
    return text + '"' if in_string else text


def _balance_brackets(text: str) -> str:
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()
    while stack:
        text += stack.pop()
    return text
