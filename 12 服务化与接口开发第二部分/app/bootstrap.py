"""Path bootstrap for stage 12.

- Stage-12 root is first on ``sys.path`` so ``import app`` resolves **here**.
- Upstream stage ``src`` packages (05–10) are mounted like stage 11.
- Stage-11 FastAPI routers / deps are loaded via :mod:`app.bridge11` (path swap),
  not by putting stage 11 ahead of stage 12 on ``sys.path``.
"""

from __future__ import annotations

import os
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


def safe_path(path: Path | str | None = None) -> Path:
    """Absolute path without Windows TxF ``resolve()`` (avoids WinError 6714 in Jupyter)."""
    raw = os.getcwd() if path is None else str(path)
    try:
        return Path(raw).resolve()
    except OSError:
        return Path(os.path.abspath(raw))


def safe_is_dir(path: Path | str) -> bool:
    try:
        return Path(path).is_dir()
    except OSError:
        return os.path.isdir(str(path))


def project_root(start: Path | None = None) -> Path:
    """Resolve repository root ``谷歌/`` from common execution locations."""
    p = safe_path(start) if start is not None else safe_path()
    if p.name == "notebooks":
        return p.parent.parent
    if p.name == STAGE12_DIR_NAME:
        return p.parent
    if safe_is_dir(p / STAGE12_DIR_NAME):
        return p
    if p.parent.name == STAGE12_DIR_NAME:
        return p.parent.parent
    if safe_is_dir(p.parent / STAGE12_DIR_NAME):
        return p.parent
    for cand in [p, *p.parents]:
        if safe_is_dir(cand / STAGE12_DIR_NAME) and safe_is_dir(cand / STAGE11_DIR_NAME):
            return cand
    return p


def stage12_dir(start: Path | None = None) -> Path:
    return project_root(start) / STAGE12_DIR_NAME


def stage11_dir(start: Path | None = None) -> Path:
    return project_root(start) / STAGE11_DIR_NAME


def _insert_front(path: Path) -> None:
    sp = str(safe_path(path))
    while sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)


_UPSTREAM_PATH_MARKERS = (
    "05 检索系统开发第一部分",
    "06 检索系统开发第二部分",
    "07 生成模块与提示词工程第一部分",
    "08 生成模块与提示词工程第二部分",
    "09 生成答案评估，缓存策略与批量处理",
    STAGE10_DIR_NAME,
    STAGE11_DIR_NAME,
)


def purge_upstream_sys_path() -> list[str]:
    """Drop stage 05–11 entries from ``sys.path`` (Jupyter leftover → WinError 6714)."""
    kept: list[str] = []
    removed: list[str] = []
    for p in sys.path:
        if any(m in p.replace("/", "\\") for m in _UPSTREAM_PATH_MARKERS):
            removed.append(p)
        else:
            kept.append(p)
    sys.path[:] = kept
    return removed


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
        if safe_is_dir(src):
            _insert_front(src)

    _insert_front(paths["stage12"])
    return paths
