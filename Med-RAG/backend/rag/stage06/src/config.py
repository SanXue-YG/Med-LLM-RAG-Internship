"""06 阶段路径、向量库与模型默认配置（Med-RAG 自包含版）。

全部资产只读 ``Med-RAG/data/``；stage04/05 src 指向 ``backend/rag/stageXX``。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Literal

_STAGE06_SRC = Path(__file__).resolve().parent
_RAG_ROOT = _STAGE06_SRC.parents[1]  # backend/rag
_BACKEND = _RAG_ROOT.parent
_HOME = _BACKEND.parent

if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

try:
    from paths import (  # type: ignore
        BM25_FULL_DIR as DATASET_BM25_FULL,
        CHROMA_FULL_DIR as DATASET_CHROMA_FULL,
        CHROMA_SAMPLE_DIR as DATASET_CHROMA_SAMPLE,
        CHUNKS_FULL_JSONL as DATASET_CHUNKS_FULL,
        CHUNKS_SAMPLE_JSONL as DATASET_CHUNKS_SAMPLE,
        DATASET_ROOT,
        SLIM_JSONL as DATASET_SLIM,
        STAGE04_SRC,
        STAGE05_SRC,
    )
except ImportError:  # pragma: no cover
    _override = os.getenv("MED_RAG_DATASET_ROOT", "").strip()
    DATASET_ROOT = Path(_override) if _override else _HOME / "data"
    DATASET_CHROMA_FULL = DATASET_ROOT / "chroma" / "chroma_db_full"
    DATASET_CHROMA_SAMPLE = DATASET_ROOT / "chroma" / "chroma_db"
    DATASET_BM25_FULL = DATASET_ROOT / "bm25" / "bm25_full"
    DATASET_CHUNKS_FULL = DATASET_ROOT / "processed" / "oa_comm_chunks.jsonl"
    DATASET_CHUNKS_SAMPLE = DATASET_ROOT / "processed" / "chunks_sample.jsonl"
    DATASET_SLIM = DATASET_ROOT / "processed" / "oa_comm_slim.jsonl"
    STAGE04_SRC = _RAG_ROOT / "stage04" / "src"
    STAGE05_SRC = _RAG_ROOT / "stage05" / "src"

PROJECT_ROOT = _HOME
STAGE06 = _RAG_ROOT / "stage06"

CHUNKS_SAMPLE_DATASET = DATASET_CHUNKS_SAMPLE
CHUNKS_FULL_DATASET = DATASET_CHUNKS_FULL
CHROMA_SAMPLE_DATASET = DATASET_CHROMA_SAMPLE
CHROMA_FULL_DATASET = DATASET_CHROMA_FULL
SLIM_DATASET = DATASET_SLIM
BM25_FULL_DATASET = DATASET_BM25_FULL

COLLECTION_SAMPLE = "pmc_oa_comm_sample"
COLLECTION_FULL = "pmc_oa_comm_full"

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-base"
DEFAULT_FUSION_STRATEGY = "rrf"

Mode = Literal["sample", "full"]


def _first_existing_file(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def _first_existing_dir(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_dir():
            return path
    return None


def resolve_chunks_path(mode: Mode = "sample") -> Path:
    if mode == "full":
        found = _first_existing_file(CHUNKS_FULL_DATASET)
        return found if found is not None else CHUNKS_FULL_DATASET
    found = _first_existing_file(CHUNKS_SAMPLE_DATASET)
    return found if found is not None else CHUNKS_SAMPLE_DATASET


def resolve_chroma(mode: Mode = "sample") -> tuple[Path, str]:
    if mode == "full":
        persist = _first_existing_dir(CHROMA_FULL_DATASET)
        return (persist if persist is not None else CHROMA_FULL_DATASET), COLLECTION_FULL
    persist = _first_existing_dir(CHROMA_SAMPLE_DATASET)
    return (persist if persist is not None else CHROMA_SAMPLE_DATASET), COLLECTION_SAMPLE


def stage04_src() -> Path:
    return STAGE04_SRC


def stage05_src() -> Path:
    return STAGE05_SRC


def resolve_slim_path() -> Path:
    found = _first_existing_file(SLIM_DATASET)
    return found if found is not None else SLIM_DATASET


def _bm25_dir_ready(candidate: Path) -> bool:
    manifest_path = candidate / "manifest.json"
    if not manifest_path.is_file():
        return False
    if (candidate / "bm25_index.pkl").is_file():
        return True
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    return manifest.get("format") == "bm25_sharded_v1" and manifest.get("status") in (
        "completed",
        "already_completed",
    )


def resolve_bm25_cache_dir(mode: Mode = "sample") -> Path | None:
    if mode != "full":
        return None
    if BM25_FULL_DATASET.is_dir() and _bm25_dir_ready(BM25_FULL_DATASET):
        return BM25_FULL_DATASET
    return None
