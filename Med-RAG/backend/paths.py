"""Med-RAG canonical data paths — all runtime assets under ``Med-RAG/data/``.

Environment:
  ``MED_RAG_HOME`` — package root (default: parent of ``backend/``)
  ``MED_RAG_DATASET_ROOT`` — override data root (default: ``<home>/data``)
"""

from __future__ import annotations

import os
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_HOME = _BACKEND_DIR.parent


def med_rag_home() -> Path:
    override = os.getenv("MED_RAG_HOME", "").strip()
    if override:
        return Path(override).resolve()
    return _DEFAULT_HOME.resolve()


def dataset_root() -> Path:
    override = os.getenv("MED_RAG_DATASET_ROOT", "").strip()
    if override:
        return Path(override).resolve()
    return med_rag_home() / "data"


MED_RAG_HOME = med_rag_home()
DATASET_ROOT = dataset_root()

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
CHAT_DIR = DATASET_ROOT / "chat"
RAW_UPLOADS_DIR = DATASET_ROOT / "raw_uploads"
LEXICONS_DIR = DATASET_ROOT / "lexicons"
LOG_DIR = DATASET_ROOT / "logs"
MEDICAL_SYNONYMS_JSON = LEXICONS_DIR / "medical_synonyms.json"

COLLECTION_SAMPLE = "pmc_oa_comm_sample"
COLLECTION_FULL = "pmc_oa_comm_full"

# Vendored RAG stage roots (self-contained; no dependency on repo stage folders)
RAG_ROOT = _BACKEND_DIR / "rag"
STAGE04_SRC = RAG_ROOT / "stage04" / "src"
STAGE05_SRC = RAG_ROOT / "stage05" / "src"
STAGE05_DATA = RAG_ROOT / "stage05" / "data"
STAGE06_SRC = RAG_ROOT / "stage06" / "src"
STAGE07_SRC = RAG_ROOT / "stage07" / "src"
STAGE08_SRC = RAG_ROOT / "stage08" / "src"
STAGE10_SRC = RAG_ROOT / "stage10" / "src"


def index_ready(mode: str = "sample") -> dict:
    """Probe whether retrieval assets exist for the given mode."""
    mode = (mode or "sample").strip().lower()
    if mode == "full":
        chroma = CHROMA_FULL_DIR
        chunks = CHUNKS_FULL_JSONL
        docs = DOCUMENTS_FULL_SQLITE
        collection = COLLECTION_FULL
    else:
        chroma = CHROMA_SAMPLE_DIR
        chunks = CHUNKS_SAMPLE_JSONL
        docs = DOCUMENTS_SAMPLE_SQLITE
        collection = COLLECTION_SAMPLE
    return {
        "mode": mode,
        "collection": collection,
        "chroma_exists": chroma.is_dir(),
        "chroma_dir": str(chroma),
        "chunks_exists": chunks.is_file(),
        "chunks_path": str(chunks),
        "documents_exists": docs.is_file(),
        "documents_path": str(docs),
        "ready": chroma.is_dir() and chunks.is_file(),
    }
