"""Project path bootstrap for stage 09 notebooks/scripts.

Loads required stage source paths in a deterministic order.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict


class StagePaths(TypedDict):
    root: Path
    stage06: Path
    stage07: Path
    stage08: Path
    stage09: Path


def project_root(start: Path | None = None) -> Path:
    """Resolve repository root ``谷歌/`` from common execution locations."""
    p = (start or Path.cwd()).resolve()
    if p.name == "notebooks":
        return p.parent.parent
    if p.name == "09 生成答案评估，缓存策略与批量处理":
        return p.parent
    if (p / "09 生成答案评估，缓存策略与批量处理").is_dir():
        return p
    return p.parent if (p.parent / "08 生成模块与提示词工程第二部分").is_dir() else p


def bootstrap_paths(start: Path | None = None) -> StagePaths:
    """Insert stage src paths into ``sys.path`` (priority: 09 > 08 > 07 > 06)."""
    root = project_root(start)
    paths: StagePaths = {
        "root": root,
        "stage06": root / "06 检索系统开发第二部分",
        "stage07": root / "07 生成模块与提示词工程第一部分",
        "stage08": root / "08 生成模块与提示词工程第二部分",
        "stage09": root / "09 生成答案评估，缓存策略与批量处理",
    }
    for key in ("stage06", "stage07", "stage08", "stage09"):
        src = paths[key] / "src"
        sp = str(src.resolve())
        if src.is_dir() and sp not in sys.path:
            sys.path.insert(0, sp)
    return paths

