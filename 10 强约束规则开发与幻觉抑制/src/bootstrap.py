"""Project path bootstrap for stage 10 notebooks/scripts.

Loads upstream stage ``src`` paths so 05–09 modules remain importable.
Priority when inserting: later stages first (10 > 09 > … > 05).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict


class StagePaths(TypedDict):
    root: Path
    stage05: Path
    stage06: Path
    stage07: Path
    stage08: Path
    stage09: Path
    stage10: Path


STAGE10_DIR_NAME = "10 强约束规则开发与幻觉抑制"


def project_root(start: Path | None = None) -> Path:
    """Resolve repository root ``谷歌/`` from common execution locations."""
    p = (start or Path.cwd()).resolve()
    if p.name == "notebooks":
        return p.parent.parent
    if p.name == STAGE10_DIR_NAME:
        return p.parent
    if (p / STAGE10_DIR_NAME).is_dir():
        return p
    # scripts/ or tests/ under stage 10
    if p.parent.name == STAGE10_DIR_NAME:
        return p.parent.parent
    if (p.parent / STAGE10_DIR_NAME).is_dir():
        return p.parent
    return p


def bootstrap_paths(start: Path | None = None) -> StagePaths:
    """Insert stage ``src`` dirs into ``sys.path``.

    Paths are (re)inserted in order 05→…→10 with ``insert(0, …)`` so
    **stage 10 ends first** and wins name clashes (e.g. ``config``).
    """
    root = project_root(start)
    paths: StagePaths = {
        "root": root,
        "stage05": root / "05 检索系统开发第一部分",
        "stage06": root / "06 检索系统开发第二部分",
        "stage07": root / "07 生成模块与提示词工程第一部分",
        "stage08": root / "08 生成模块与提示词工程第二部分",
        "stage09": root / "09 生成答案评估，缓存策略与批量处理",
        "stage10": root / STAGE10_DIR_NAME,
    }
    for key in ("stage05", "stage06", "stage07", "stage08", "stage09", "stage10"):
        src = paths[key] / "src"
        if not src.is_dir():
            continue
        sp = str(src.resolve())
        while sp in sys.path:
            sys.path.remove(sp)
        sys.path.insert(0, sp)
    return paths
