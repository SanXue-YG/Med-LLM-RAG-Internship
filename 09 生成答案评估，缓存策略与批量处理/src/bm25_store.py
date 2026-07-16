"""Stage 09: full-corpus BM25 offline index build/load helpers."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

CORPUS_SIZE_HINT = 6_107_296

STAGE09_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = STAGE09_ROOT.parent
# 默认写入统一 Dataset；legacy 09/data 仅兼容旧环境
BM25_FULL_CACHE_DIR = PROJECT_ROOT / "Dataset" / "bm25" / "bm25_full"
BM25_FULL_CACHE_LEGACY = STAGE09_ROOT / "data" / "bm25_full"
CHUNKS_FULL_JSONL = PROJECT_ROOT / "Dataset" / "processed" / "oa_comm_chunks.jsonl"
CHUNKS_FULL_JSONL_LEGACY = STAGE09_ROOT / "data" / "oa_comm_chunks.jsonl"
BM25_FULL_BACKUP_E = Path(r"E:\med-llm-rag-datasets\bm25_full")  # 手动备份目标，不参与自动读取
CHUNKS_FULL_BACKUP_E = Path(r"E:\med-llm-rag-datasets\processed\oa_comm_chunks.jsonl")  # 手动备份，不参与自动读取


def resolve_bm25_full_cache_dir() -> Path:
    """默认落盘/读取路径：``Dataset/bm25/bm25_full``（可用环境变量覆盖）。"""
    import os

    override = os.getenv("STAGE09_BM25_FULL_DIR", "").strip()
    if override:
        return Path(override)
    if BM25_FULL_CACHE_DIR.is_dir():
        return BM25_FULL_CACHE_DIR
    if BM25_FULL_CACHE_LEGACY.is_dir():
        return BM25_FULL_CACHE_LEGACY
    return BM25_FULL_CACHE_DIR

def _load_stage06_config(stage06: Path) -> Any:
    import importlib.util

    path = stage06 / "src" / "config.py"
    spec = importlib.util.spec_from_file_location("stage06_config_bm25", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load stage06 config: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_stage06_src(stage06: Path) -> None:
    src = str((stage06 / "src").resolve())
    if src not in sys.path:
        sys.path.insert(0, src)
    # stage09 config shadows stage06 config when both are on path
    cfg = _load_stage06_config(stage06)
    sys.modules["config"] = cfg


def cache_status(stage06: Path) -> dict[str, Any]:
    """检查离线索引是否已存在且与源 JSONL 一致。"""
    _ensure_stage06_src(stage06)
    from config import resolve_bm25_cache_dir, resolve_chunks_path  # type: ignore[import-not-found]

    cache_dir = resolve_bm25_cache_dir("full")
    source = resolve_chunks_path("full")
    if cache_dir is None:
        return {
            "ready": False,
            "cache_dir": str(resolve_bm25_full_cache_dir()),
            "source_jsonl": str(source),
            "source_exists": source.is_file(),
            "message": "offline BM25 cache not found",
        }

    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
    stale = False
    stale_reason = ""
    if source.is_file():
        if manifest.get("source_size_bytes") != source.stat().st_size:
            stale = True
            stale_reason = "source_size_changed"
        elif manifest.get("source_mtime") != source.stat().st_mtime:
            stale = True
            stale_reason = "source_mtime_changed"

    return {
        "ready": not stale,
        "stale": stale,
        "stale_reason": stale_reason,
        "cache_dir": str(cache_dir),
        "manifest": manifest,
        "source_jsonl": str(source),
        "source_exists": source.is_file(),
    }


def build_and_save_full_bm25(
    stage06: Path,
    *,
    output_dir: Path | None = None,
    limit: int | None = None,
    validate_source: bool = True,
) -> dict[str, Any]:
    """（旧）单体构建 BM25 并落盘。大规模建议改用 ``build_sharded_full_bm25``。"""
    _ensure_stage06_src(stage06)
    from bm25_index import BM25Index  # type: ignore[import-not-found]
    from config import resolve_chunks_path  # type: ignore[import-not-found]

    source = resolve_chunks_path("full")
    out_dir = output_dir or resolve_bm25_full_cache_dir()
    started = time.perf_counter()

    index = BM25Index()
    count = index.build_from_jsonl(source, limit=limit)
    saved_dir = index.save(out_dir)

    elapsed = round(time.perf_counter() - started, 2)
    manifest = json.loads((saved_dir / "manifest.json").read_text(encoding="utf-8"))
    return {
        "status": "ok",
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "chunk_count": count,
        "elapsed_seconds": elapsed,
        "source_jsonl": str(source),
        "cache_dir": str(saved_dir),
        "manifest": manifest,
        "payload_bytes": (saved_dir / "bm25_index.pkl").stat().st_size,
    }


def build_sharded_full_bm25(
    stage06: Path,
    *,
    output_dir: Path | None = None,
    shard_size: int = 200_000,
    resume: bool = True,
    limit: int | None = None,
    progress_cb: Any = None,
) -> dict[str, Any]:
    """分片构建全量 BM25（低内存、断点续建、进度输出）。"""
    _ensure_stage06_src(stage06)
    from bm25_sharded import build_sharded_bm25  # type: ignore[import-not-found]
    from config import resolve_chunks_path  # type: ignore[import-not-found]

    source = resolve_chunks_path("full")
    out_dir = output_dir or resolve_bm25_full_cache_dir()
    manifest = build_sharded_bm25(
        source,
        out_dir,
        shard_size=shard_size,
        resume=resume,
        limit=limit,
        progress_cb=progress_cb,
    )
    manifest.setdefault("cache_dir", str(out_dir))
    manifest.setdefault("source_jsonl", str(source))
    return manifest


def sharded_status(stage06: Path, *, output_dir: Path | None = None) -> dict[str, Any]:
    """展示分片索引构建状态（含断点进度）。"""
    _ensure_stage06_src(stage06)
    from bm25_sharded import cache_progress  # type: ignore[import-not-found]

    out_dir = output_dir or resolve_bm25_full_cache_dir()
    return cache_progress(out_dir)
