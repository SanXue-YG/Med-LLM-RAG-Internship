"""06 阶段路径、向量库与模型默认配置。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

STAGE06 = Path(__file__).resolve().parents[1]
PROJECT_ROOT = STAGE06.parent

STAGE03 = PROJECT_ROOT / "03 文档解析与分割"
STAGE04 = PROJECT_ROOT / "04 向量化与索引构建"
STAGE05 = PROJECT_ROOT / "05 检索系统开发第一部分"
STAGE09 = PROJECT_ROOT / "09 生成答案评估，缓存策略与批量处理"

# --- BM25 语料（chunks JSONL）---
CHUNKS_SAMPLE = STAGE03 / "data" / "processed" / "chunks_sample.jsonl"
CHUNKS_SAMPLE_04 = STAGE04 / "data" / "processed" / "chunks_sample.jsonl"
CHUNKS_FULL_STAGE09 = STAGE09 / "data" / "oa_comm_chunks.jsonl"
CHUNKS_FULL_LOCAL_04 = STAGE04 / "data" / "processed" / "oa_comm_chunks.jsonl"
CHUNKS_FULL_BACKUP = Path(r"E:\med-llm-rag-datasets\processed\oa_comm_chunks.jsonl")

# --- Chroma 向量库（复用 04）---
CHROMA_SAMPLE_DIR = STAGE04 / "data" / "chroma_db"
CHROMA_FULL_DIR = STAGE04 / "data" / "chroma_db_full"
CHROMA_FULL_BACKUP = Path(r"E:\med-llm-rag-datasets\chroma_db_full")

COLLECTION_SAMPLE = "pmc_oa_comm_sample"
COLLECTION_FULL = "pmc_oa_comm_full"

# --- 文献元数据（重排 recency/authority 回查，02 slim）---
SLIM_LOCAL = STAGE06 / "data" / "oa_comm_slim.jsonl"
SLIM_FULL_BACKUP = Path(r"E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl")

# --- BM25 全量离线索引（09 阶段构建；默认读写 09/data，E: 仅手动备份）---
BM25_FULL_CACHE = STAGE09 / "data" / "bm25_full"
BM25_FULL_BACKUP = Path(r"E:\med-llm-rag-datasets\bm25_full")  # 不参与自动 resolve

# --- 模型（与 04/05 一致）---
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "BAAI/bge-reranker-base"

# --- 融合默认 ---
DEFAULT_FUSION_STRATEGY = "rrf"

Mode = Literal["sample", "full"]


def resolve_chunks_path(mode: Mode = "sample") -> Path:
    """返回 BM25 建索引用的 chunks JSONL 路径。"""
    if mode == "full":
        for candidate in (CHUNKS_FULL_STAGE09, CHUNKS_FULL_LOCAL_04, CHUNKS_FULL_BACKUP):
            if candidate.is_file():
                return candidate
        return CHUNKS_FULL_STAGE09
    for candidate in (CHUNKS_SAMPLE, CHUNKS_SAMPLE_04):
        if candidate.is_file():
            return candidate
    return CHUNKS_SAMPLE


def resolve_chroma(mode: Mode = "sample") -> tuple[Path, str]:
    """返回 (persist_dir, collection_name)。"""
    if mode == "full":
        persist = CHROMA_FULL_DIR if CHROMA_FULL_DIR.is_dir() else CHROMA_FULL_BACKUP
        return persist, COLLECTION_FULL
    return CHROMA_SAMPLE_DIR, COLLECTION_SAMPLE


def stage04_src() -> Path:
    """04 阶段 src 目录（挂载 DocumentEmbedder / ChromaIndexBuilder）。"""
    return STAGE04 / "src"


def stage05_src() -> Path:
    """05 阶段 src 目录（挂载 MedicalQueryEnhancer）。"""
    return STAGE05 / "src"


def resolve_slim_path() -> Path:
    """返回 slim JSONL 路径（优先本阶段本地副本，回退 E: 权威源）。"""
    if SLIM_LOCAL.is_file():
        return SLIM_LOCAL
    if SLIM_FULL_BACKUP.is_file():
        return SLIM_FULL_BACKUP
    return SLIM_LOCAL


def resolve_bm25_cache_dir(mode: Mode = "sample") -> Path | None:
    """返回可加载的 BM25 离线索引目录（仅 09/data/bm25_full）；不存在/未完成则 None。

    支持两种格式：
    - 单体：``bm25_index.pkl`` + ``manifest.json``
    - 分片：``manifest.json``（``format=bm25_sharded_v1`` 且 ``status=completed``）
    """
    if mode != "full":
        return None
    candidate = BM25_FULL_CACHE
    manifest_path = candidate / "manifest.json"

    if manifest_path.is_file() and (candidate / "bm25_index.pkl").is_file():
        return candidate

    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None
        if (
            manifest.get("format") == "bm25_sharded_v1"
            and manifest.get("status") in ("completed", "already_completed")
        ):
            return candidate
    return None
