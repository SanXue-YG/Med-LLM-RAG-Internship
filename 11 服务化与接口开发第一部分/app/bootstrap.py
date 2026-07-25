"""Path bootstrap for stage 11 — mount upstream stage ``src`` packages.

Insert order 05→…→10 with ``insert(0, …)`` so **stage 10 wins** name clashes
(e.g. ``config`` / ``bootstrap``), matching stage-10 practice.
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
    stage11: Path


STAGE11_DIR_NAME = "11 服务化与接口开发第一部分"
STAGE10_DIR_NAME = "10 强约束规则开发与幻觉抑制"


def project_root(start: Path | None = None) -> Path:
    """Resolve repository root ``谷歌/`` from common execution locations."""
    p = (start or Path.cwd()).resolve()
    if p.name == "notebooks":
        return p.parent.parent
    if p.name == STAGE11_DIR_NAME:
        return p.parent
    if (p / STAGE11_DIR_NAME).is_dir():
        return p
    if p.parent.name == STAGE11_DIR_NAME:
        return p.parent.parent
    if (p.parent / STAGE11_DIR_NAME).is_dir():
        return p.parent
    # Fallback: walk up looking for stage 11 sibling marker
    for cand in [p, *p.parents]:
        if (cand / STAGE11_DIR_NAME).is_dir() and (cand / STAGE10_DIR_NAME).is_dir():
            return cand
    return p


def stage11_dir(start: Path | None = None) -> Path:
    root = project_root(start)
    return root / STAGE11_DIR_NAME


def bootstrap_paths(start: Path | None = None) -> StagePaths:
    """Insert upstream ``src`` dirs and ensure stage-11 root is importable as ``app``."""
    root = project_root(start)
    paths: StagePaths = {
        "root": root,
        "stage05": root / "05 检索系统开发第一部分",
        "stage06": root / "06 检索系统开发第二部分",
        "stage07": root / "07 生成模块与提示词工程第一部分",
        "stage08": root / "08 生成模块与提示词工程第二部分",
        "stage09": root / "09 生成答案评估，缓存策略与批量处理",
        "stage10": root / STAGE10_DIR_NAME,
        "stage11": root / STAGE11_DIR_NAME,
    }

    # Stage 11 root first so ``import app`` works from notebooks/tests/scripts.
    stage11_root = str(paths["stage11"].resolve())
    while stage11_root in sys.path:
        sys.path.remove(stage11_root)
    sys.path.insert(0, stage11_root)

    for key in ("stage05", "stage06", "stage07", "stage08", "stage09", "stage10"):
        src = paths[key] / "src"
        if not src.is_dir():
            continue
        sp = str(src.resolve())
        while sp in sys.path:
            sys.path.remove(sp)
        sys.path.insert(0, sp)

    # Re-assert stage 11 ahead of upstream src (app package must not be shadowed).
    while stage11_root in sys.path:
        sys.path.remove(stage11_root)
    sys.path.insert(0, stage11_root)
    return paths
