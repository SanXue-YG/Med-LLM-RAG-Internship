"""Project path bootstrap for Med-RAG vendored stage 10.

Loads sibling vendored stage ``src`` paths under ``Med-RAG/backend/rag/``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict


class StagePaths(TypedDict):
    home: Path
    stage05: Path
    stage06: Path
    stage07: Path
    stage08: Path
    stage10: Path


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "deepseek-r1:7b"


def med_rag_home(start: Path | None = None) -> Path:
    # …/Med-RAG/backend/rag/stage10/src/bootstrap.py
    # parents: 0=src 1=stage10 2=rag 3=backend 4=Med-RAG
    return Path(__file__).resolve().parents[4]


def bootstrap_paths(start: Path | None = None) -> StagePaths:
    home = med_rag_home(start)
    backend = home / "backend"
    rag = backend / "rag"
    paths: StagePaths = {
        "home": home,
        "stage05": rag / "stage05",
        "stage06": rag / "stage06",
        "stage07": rag / "stage07",
        "stage08": rag / "stage08",
        "stage10": rag / "stage10",
    }

    for p in (str(backend.resolve()), str(home.resolve())):
        while p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)

    try:
        import paths as _med_paths  # noqa: F401
        sys.modules.setdefault("dataset_paths", sys.modules["paths"])
    except Exception:
        pass

    for key in ("stage05", "stage06", "stage07", "stage08", "stage10"):
        src = paths[key] / "src"
        if not src.is_dir():
            continue
        sp = str(src.resolve())
        while sp in sys.path:
            sys.path.remove(sp)
        sys.path.insert(0, sp)
    return paths


# Alias used by some upstream helpers
project_root = med_rag_home
