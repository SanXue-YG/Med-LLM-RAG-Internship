"""Canonical large-asset paths under ``<repo>/Dataset/``.

New code should import from here (or from stage-06 ``config.resolve_*``, which
prefers these paths) instead of hardcoding stage ``data/`` directories.

Environment override: ``MED_RAG_DATASET_ROOT`` → alternate Dataset root.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def dataset_root() -> Path:
    override = os.getenv("MED_RAG_DATASET_ROOT", "").strip()
    if override:
        return Path(override)
    return REPO_ROOT / "Dataset"


DATASET_ROOT = dataset_root()

# Layout (see Dataset/README.md)
CHROMA_FULL_DIR = DATASET_ROOT / "chroma" / "chroma_db_full"
CHROMA_SAMPLE_DIR = DATASET_ROOT / "chroma" / "chroma_db"
BM25_FULL_DIR = DATASET_ROOT / "bm25" / "bm25_full"
CHUNKS_FULL_JSONL = DATASET_ROOT / "processed" / "oa_comm_chunks.jsonl"
CHUNKS_SAMPLE_JSONL = DATASET_ROOT / "processed" / "chunks_sample.jsonl"
SLIM_JSONL = DATASET_ROOT / "processed" / "oa_comm_slim.jsonl"
DOCUMENTS_DIR = DATASET_ROOT / "documents"
DOCUMENTS_SAMPLE_DIR = DOCUMENTS_DIR / "sample"
DOCUMENTS_FULL_DIR = DOCUMENTS_DIR / "full"
DOCUMENTS_SAMPLE_SQLITE = DOCUMENTS_SAMPLE_DIR / "documents_sample.sqlite"
DOCUMENTS_FULL_SQLITE = DOCUMENTS_FULL_DIR / "documents_full.sqlite"

COLLECTION_SAMPLE = "pmc_oa_comm_sample"
COLLECTION_FULL = "pmc_oa_comm_full"
