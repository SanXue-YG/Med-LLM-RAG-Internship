"""项目路径引导：notebook / 脚本共用。

注意：勿将 05/src 提前加入 sys.path，否则会与 07 的 ``models`` 模块冲突。
05 模块由 06 ``RetrievalPipeline`` 在实例化时按需挂载。
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


def project_root(start: Path | None = None) -> Path:
    """解析仓库根目录 ``谷歌/``。"""
    p = (start or Path.cwd()).resolve()
    if p.name == "notebooks":
        return p.parent.parent
    if p.name == "08 生成模块与提示词工程第二部分":
        return p.parent
    if (p / "08 生成模块与提示词工程第二部分").is_dir():
        return p
    return p.parent if (p.parent / "06 检索系统开发第二部分").is_dir() else p


def bootstrap_paths(start: Path | None = None) -> StagePaths:
    """将 08 / 06 / 07 的 ``src`` 加入 ``sys.path``（优先级 08 > 06 > 07）。"""
    root = project_root(start)
    paths: StagePaths = {
        "root": root,
        "stage05": root / "05 检索系统开发第一部分",
        "stage06": root / "06 检索系统开发第二部分",
        "stage07": root / "07 生成模块与提示词工程第一部分",
        "stage08": root / "08 生成模块与提示词工程第二部分",
    }
    for key in ("stage07", "stage06", "stage08"):
        src = paths[key] / "src"
        sp = str(src.resolve())
        if src.is_dir() and sp not in sys.path:
            sys.path.insert(0, sp)
    return paths


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "deepseek-r1:7b"
