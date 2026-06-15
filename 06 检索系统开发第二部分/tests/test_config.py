import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from config import (  # noqa: E402
    CHUNKS_SAMPLE,
    COLLECTION_FULL,
    COLLECTION_SAMPLE,
    EMBED_MODEL,
    RERANK_MODEL,
    resolve_chroma,
    resolve_chunks_path,
    resolve_slim_path,
)


def test_sample_chunks_exists():
    path = resolve_chunks_path("sample")
    assert path.is_file(), f"sample chunks missing: {path}"


def test_sample_chroma_paths():
    persist, collection = resolve_chroma("sample")
    assert collection == COLLECTION_SAMPLE
    assert persist.name in ("chroma_db", "chroma_db_full")


def test_full_chroma_defaults():
    persist, collection = resolve_chroma("full")
    assert collection == COLLECTION_FULL
    assert persist.exists() or persist.parent.exists()


def test_model_names():
    assert "bge-small-en" in EMBED_MODEL
    assert "bge-reranker" in RERANK_MODEL


def test_chunks_sample_constant():
    assert CHUNKS_SAMPLE.suffix == ".jsonl"


def test_slim_path_prefers_local():
    slim = resolve_slim_path()
    assert slim.name == "oa_comm_slim.jsonl"
    assert slim.is_file(), f"slim missing: {slim}"
