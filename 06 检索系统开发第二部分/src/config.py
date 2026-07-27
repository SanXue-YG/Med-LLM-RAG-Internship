"""06 阶段路径、向量库与模型默认配置。

大数据资产默认在仓库根 ``Dataset/``（见根目录 ``dataset_paths.py``）；
旧阶段 ``data/`` 与 ``E:\\med-llm-rag-datasets`` 仅作兼容回退。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Literal

STAGE06 = Path(__file__).resolve().parents[1]
PROJECT_ROOT = STAGE06.parent

STAGE03 = PROJECT_ROOT / "03 文档解析与分割"
STAGE04 = PROJECT_ROOT / "04 向量化与索引构建"
STAGE05 = PROJECT_ROOT / "05 检索系统开发第一部分"
STAGE09 = PROJECT_ROOT / "09 生成答案评估，缓存策略与批量处理"

# --- 统一 Dataset（新代码 / 默认主路径）---
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
try:
    from dataset_paths import (  # type: ignore[import-not-found]
        BM25_FULL_DIR as DATASET_BM25_FULL,
        CHROMA_FULL_DIR as DATASET_CHROMA_FULL,
        CHROMA_SAMPLE_DIR as DATASET_CHROMA_SAMPLE,
        CHUNKS_FULL_JSONL as DATASET_CHUNKS_FULL,
        CHUNKS_SAMPLE_JSONL as DATASET_CHUNKS_SAMPLE,
        DATASET_ROOT,
        SLIM_JSONL as DATASET_SLIM,
    )
except ImportError:  # pragma: no cover - flat copy without repo root
    _override = os.getenv("MED_RAG_DATASET_ROOT", "").strip()
    DATASET_ROOT = Path(_override) if _override else PROJECT_ROOT / "Dataset"
    DATASET_CHROMA_FULL = DATASET_ROOT / "chroma" / "chroma_db_full"
    DATASET_CHROMA_SAMPLE = DATASET_ROOT / "chroma" / "chroma_db"
    DATASET_BM25_FULL = DATASET_ROOT / "bm25" / "bm25_full"
    DATASET_CHUNKS_FULL = DATASET_ROOT / "processed" / "oa_comm_chunks.jsonl"
    DATASET_CHUNKS_SAMPLE = DATASET_ROOT / "processed" / "chunks_sample.jsonl"
    DATASET_SLIM = DATASET_ROOT / "processed" / "oa_comm_slim.jsonl"

# --- BM25 语料（chunks JSONL）---
CHUNKS_SAMPLE_DATASET = DATASET_CHUNKS_SAMPLE
CHUNKS_SAMPLE = STAGE03 / "data" / "processed" / "chunks_sample.jsonl"
CHUNKS_SAMPLE_04 = STAGE04 / "data" / "processed" / "chunks_sample.jsonl"
CHUNKS_FULL_DATASET = DATASET_CHUNKS_FULL
CHUNKS_FULL_STAGE09 = STAGE09 / "data" / "oa_comm_chunks.jsonl"
CHUNKS_FULL_LOCAL_04 = STAGE04 / "data" / "processed" / "oa_comm_chunks.jsonl"
CHUNKS_FULL_BACKUP = Path(r"E:\med-llm-rag-datasets\processed\oa_comm_chunks.jsonl")

# --- Chroma 向量库 ---
CHROMA_SAMPLE_DATASET = DATASET_CHROMA_SAMPLE
CHROMA_SAMPLE_DIR = STAGE04 / "data" / "chroma_db"  # legacy
CHROMA_FULL_DATASET = DATASET_CHROMA_FULL
CHROMA_FULL_DIR = STAGE04 / "data" / "chroma_db_full"  # legacy
CHROMA_FULL_BACKUP = Path(r"E:\med-llm-rag-datasets\chroma_db_full")

COLLECTION_SAMPLE = "pmc_oa_comm_sample"
COLLECTION_FULL = "pmc_oa_comm_full"

# --- 文献元数据（重排 recency/authority 回查，02 slim）---
SLIM_DATASET = DATASET_SLIM
SLIM_LOCAL = STAGE06 / "data" / "oa_comm_slim.jsonl"  # legacy
SLIM_FULL_BACKUP = Path(r"E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl")

# --- BM25 全量离线索引 ---
BM25_FULL_DATASET = DATASET_BM25_FULL
BM25_FULL_CACHE = STAGE09 / "data" / "bm25_full"  # legacy
BM25_FULL_BACKUP = Path(r"E:\med-llm-rag-datasets\bm25_full")

# --- 模型（与 04/05 一致）---
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-base"

# --- 融合默认 ---
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
    """返回 BM25 建索引用的 chunks JSONL 路径（优先 Dataset）。"""
    if mode == "full":
        found = _first_existing_file(
            CHUNKS_FULL_DATASET,
            CHUNKS_FULL_STAGE09,
            CHUNKS_FULL_LOCAL_04,
            CHUNKS_FULL_BACKUP,
        )
        return found if found is not None else CHUNKS_FULL_DATASET
    found = _first_existing_file(CHUNKS_SAMPLE_DATASET, CHUNKS_SAMPLE, CHUNKS_SAMPLE_04)
    return found if found is not None else CHUNKS_SAMPLE_DATASET


def resolve_chroma(mode: Mode = "sample") -> tuple[Path, str]:
    """返回 (persist_dir, collection_name)（优先 Dataset）。"""
    if mode == "full":
        persist = _first_existing_dir(
            CHROMA_FULL_DATASET,
            CHROMA_FULL_DIR,
            CHROMA_FULL_BACKUP,
        )
        return (persist if persist is not None else CHROMA_FULL_DATASET), COLLECTION_FULL
    persist = _first_existing_dir(CHROMA_SAMPLE_DATASET, CHROMA_SAMPLE_DIR)
    return (persist if persist is not None else CHROMA_SAMPLE_DATASET), COLLECTION_SAMPLE


def stage04_src() -> Path:
    """04 阶段 src 目录（挂载 DocumentEmbedder / ChromaIndexBuilder）。"""
    return STAGE04 / "src"


def stage05_src() -> Path:
    """05 阶段 src 目录（挂载 MedicalQueryEnhancer）。"""
    return STAGE05 / "src"


def resolve_slim_path() -> Path:
    """返回 slim JSONL 路径（优先 Dataset，回退 legacy / E:）。"""
    found = _first_existing_file(SLIM_DATASET, SLIM_LOCAL, SLIM_FULL_BACKUP)
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
    """返回可加载的 BM25 离线索引目录（优先 Dataset/bm25/bm25_full）。

    支持两种格式：
    - 单体：``bm25_index.pkl`` + ``manifest.json``
    - 分片：``manifest.json``（``format=bm25_sharded_v1`` 且 ``status=completed``）
    """
    if mode != "full":
        return None
    for candidate in (BM25_FULL_DATASET, BM25_FULL_CACHE, BM25_FULL_BACKUP):
        if candidate.is_dir() and _bm25_dir_ready(candidate):
            return candidate
    return None
