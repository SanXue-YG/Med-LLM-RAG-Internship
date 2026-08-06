"""Path bootstrap for Med-RAG — mount vendored stage ``src`` packages only.

Insert order 05→…→10 with ``insert(0, …)`` so **stage 10 wins** name clashes
(e.g. ``config`` / ``bootstrap``). Never depends on sibling stage folders outside
``Med-RAG/``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict


class StagePaths(TypedDict):
    home: Path
    backend: Path
    stage05: Path
    stage06: Path
    stage07: Path
    stage08: Path
    stage10: Path


def med_rag_home(start: Path | None = None) -> Path:
    """Resolve ``Med-RAG/`` package root."""
    backend = Path(__file__).resolve().parent.parent  # …/Med-RAG/backend
    return backend.parent


def bootstrap_paths(start: Path | None = None) -> StagePaths:
    """Insert vendored ``rag/stageXX/src`` dirs and ensure ``backend`` is importable."""
    home = med_rag_home(start)
    backend = home / "backend"
    rag = backend / "rag"
    paths: StagePaths = {
        "home": home,
        "backend": backend,
        "stage05": rag / "stage05",
        "stage06": rag / "stage06",
        "stage07": rag / "stage07",
        "stage08": rag / "stage08",
        "stage10": rag / "stage10",
    }

    # Ensure Med-RAG paths + dataset_paths shim are importable
    for p in (str(backend.resolve()), str(home.resolve())):
        while p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)

    # Install dataset_paths shim name for upstream imports
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

    # Re-assert backend ahead so ``import app`` is not shadowed.
    backend_s = str(backend.resolve())
    while backend_s in sys.path:
        sys.path.remove(backend_s)
    sys.path.insert(0, backend_s)
    return paths
