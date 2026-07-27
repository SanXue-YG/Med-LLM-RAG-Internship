"""Path bootstrap for stage 12.

- Stage-12 root is first on ``sys.path`` so ``import app`` resolves **here**.
- Upstream stage ``src`` packages (05–10) are mounted like stage 11.
- Stage-11 FastAPI routers / deps are loaded via :mod:`app.bridge11` (path swap),
  not by putting stage 11 ahead of stage 12 on ``sys.path``.
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
    stage12: Path


STAGE12_DIR_NAME = "12 服务化与接口开发第二部分"
STAGE11_DIR_NAME = "11 服务化与接口开发第一部分"
STAGE10_DIR_NAME = "10 强约束规则开发与幻觉抑制"


def project_root(start: Path | None = None) -> Path:
    """Resolve repository root ``谷歌/`` from common execution locations."""
    p = (start or Path.cwd()).resolve()
    if p.name == "notebooks":
        return p.parent.parent
    if p.name == STAGE12_DIR_NAME:
        return p.parent
    if (p / STAGE12_DIR_NAME).is_dir():
        return p
    if p.parent.name == STAGE12_DIR_NAME:
        return p.parent.parent
    if (p.parent / STAGE12_DIR_NAME).is_dir():
        return p.parent
    for cand in [p, *p.parents]:
        if (cand / STAGE12_DIR_NAME).is_dir() and (cand / STAGE11_DIR_NAME).is_dir():
            return cand
    return p


def stage12_dir(start: Path | None = None) -> Path:
    return project_root(start) / STAGE12_DIR_NAME


def stage11_dir(start: Path | None = None) -> Path:
    return project_root(start) / STAGE11_DIR_NAME


def _insert_front(path: Path) -> None:
    sp = str(path.resolve())
    while sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)


def bootstrap_paths(start: Path | None = None) -> StagePaths:
    """Insert upstream ``src`` dirs; ensure stage-12 root is importable as ``app``."""
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
        "stage12": root / STAGE12_DIR_NAME,
    }

    for key in ("stage05", "stage06", "stage07", "stage08", "stage09", "stage10"):
        src = paths[key] / "src"
        if src.is_dir():
            _insert_front(src)

    _insert_front(paths["stage12"])
    return paths
