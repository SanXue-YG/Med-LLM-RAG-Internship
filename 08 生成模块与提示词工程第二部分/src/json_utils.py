"""JSON 提取与修复（阶段 2 将扩展 ``repair_json``）。"""

from __future__ import annotations

import json
import re


def extract_json(text: str) -> dict | None:
    """从模型文本中提取 JSON 对象（剥离 markdown 围栏）。"""
    if not text or not isinstance(text, str):
        return None

    candidates: list[str] = [text.strip()]
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        candidates.insert(0, fence.group(1).strip())

    for candidate in candidates:
        parsed = _try_parse_dict(candidate)
        if parsed is not None:
            return parsed

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return _try_parse_dict(text[start : end + 1])
    return None


def repair_json(text: str) -> str:
    """补全残缺 JSON（阶段 2 完善；当前原样返回）。"""
    return text if isinstance(text, str) else ""


def _try_parse_dict(raw: str) -> dict | None:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None
