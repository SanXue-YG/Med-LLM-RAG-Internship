"""分片 BM25：流式分片构建 + 断点续建 + 逐片查询（低内存）。

设计动机：
- `rank_bm25.BM25Okapi` 会为每个文档保存一份词频字典（``doc_freqs``），
  610 万文档一次性构建会占用极高内存，容易导致机器卡死。
- 本模块将语料按 ``shard_size`` 分片，逐片构建 ``BM25Okapi`` 并落盘后立即释放，
  构建阶段内存峰值 ≈ 单个分片；查询阶段同样逐片加载/释放。

存储布局（``out_dir``）：
- ``manifest.json``：``format=bm25_sharded_v1``、``status``、``num_shards``、``total_chunks`` 等
- ``progress.json``：断点续建进度（``completed_shards`` / ``processed_lines``）
- ``shard_00000.pkl`` ...：每片 ``{"bm25": BM25Okapi, "chunks": [...]}``

近似说明：分片后各片 IDF 基于本片文档频率，跨片 raw score 存在轻微不可比；
本索引用于**召回候选**，后续有融合 + reranker 复排，可接受该近似。
"""

from __future__ import annotations

import heapq
import json
import pickle
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from rank_bm25 import BM25Okapi

try:
    from .bm25_index import CHUNK_FIELDS, tokenize
except ImportError:  # pragma: no cover - notebook/script direct import
    from bm25_index import CHUNK_FIELDS, tokenize  # type: ignore[no-redef]

FORMAT = "bm25_sharded_v1"
MANIFEST_NAME = "manifest.json"
PROGRESS_NAME = "progress.json"
SHARD_PREFIX = "shard_"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _shard_path(out_dir: Path, idx: int) -> Path:
    return out_dir / f"{SHARD_PREFIX}{idx:05d}.pkl"


def _source_signature(source: Path) -> dict[str, Any]:
    if not source.is_file():
        return {"source_jsonl": str(source), "source_exists": False}
    st = source.stat()
    return {
        "source_jsonl": str(source),
        "source_exists": True,
        "source_size_bytes": st.st_size,
        "source_mtime": st.st_mtime,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_shard(out_dir: Path, idx: int, chunks: list[dict[str, Any]]) -> int:
    """构建单片 BM25 并落盘；返回该片文档数。构建后立即释放大对象。"""
    corpus_tokens = [tokenize(c["text"]) for c in chunks]
    corpus_tokens = [t if t else ["_empty_"] for t in corpus_tokens]
    bm25 = BM25Okapi(corpus_tokens)
    del corpus_tokens

    tmp_path = _shard_path(out_dir, idx).with_suffix(".pkl.tmp")
    with open(tmp_path, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks}, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp_path.replace(_shard_path(out_dir, idx))
    del bm25
    return len(chunks)


def build_sharded_bm25(
    jsonl_path: str | Path,
    out_dir: str | Path,
    *,
    shard_size: int = 200_000,
    resume: bool = True,
    limit: int | None = None,
    progress_cb: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """流式分片构建 BM25 索引，支持断点续建。

    Args:
        jsonl_path: 全量 chunks JSONL。
        out_dir: 输出目录（分片与 manifest/progress）。
        shard_size: 每片有效 chunk 数（越小内存峰值越低、片数越多）。
        resume: 若为 True 且已有兼容进度，从断点继续。
        limit: 仅处理前 N 个有效 chunk（smoke 用）。
        progress_cb: 每完成一片回调 dict（无回调时打印一行）。
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    source = Path(jsonl_path)
    if not source.is_file():
        raise FileNotFoundError(f"chunks JSONL not found: {source}")

    sig = _source_signature(source)
    prev = _read_json(out / PROGRESS_NAME) if resume else None

    skip_lines = 0
    shard_idx = 0
    total_chunks = 0
    fresh = True

    if (
        prev
        and prev.get("shard_size") == shard_size
        and prev.get("source_size_bytes") == sig.get("source_size_bytes")
        and prev.get("source_mtime") == sig.get("source_mtime")
    ):
        if prev.get("status") == "completed":
            manifest = _read_json(out / MANIFEST_NAME) or prev
            manifest["status"] = "already_completed"
            return manifest
        skip_lines = int(prev.get("processed_lines", 0))
        shard_idx = int(prev.get("completed_shards", 0))
        total_chunks = int(prev.get("valid_chunks", 0))
        fresh = False

    if fresh:
        for stale in out.glob(f"{SHARD_PREFIX}*.pkl"):
            stale.unlink()
        for stale in out.glob(f"{SHARD_PREFIX}*.pkl.tmp"):
            stale.unlink()
        for name in (MANIFEST_NAME, PROGRESS_NAME):
            fp = out / name
            if fp.is_file():
                fp.unlink()

    started = time.perf_counter()
    buffer: list[dict[str, Any]] = []
    line_no = 0

    def _flush() -> None:
        nonlocal shard_idx, total_chunks, buffer
        if not buffer:
            return
        count = _save_shard(out, shard_idx, buffer)
        shard_idx += 1
        total_chunks += count
        progress = {
            "status": "in_progress",
            "format": FORMAT,
            "shard_size": shard_size,
            "completed_shards": shard_idx,
            "processed_lines": line_no,
            "valid_chunks": total_chunks,
            "elapsed_seconds": round(time.perf_counter() - started, 1),
            "updated_at": _now(),
            **sig,
        }
        _write_json(out / PROGRESS_NAME, progress)
        if progress_cb is not None:
            progress_cb(progress)
        else:
            print(
                f"[bm25-shard] shard={shard_idx} "
                f"chunks_total={total_chunks} lines={line_no} "
                f"elapsed={progress['elapsed_seconds']}s",
                flush=True,
            )
        buffer = []

    with open(source, encoding="utf-8") as f:
        for line in f:
            line_no += 1
            if line_no <= skip_lines:
                continue
            if limit is not None and total_chunks + len(buffer) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            chunk = {k: row[k] for k in CHUNK_FIELDS if k in row}
            if "chunk_id" not in chunk or "text" not in chunk:
                continue
            buffer.append(chunk)
            if len(buffer) >= shard_size:
                _flush()

    _flush()

    manifest = {
        "format": FORMAT,
        "status": "completed",
        "shard_size": shard_size,
        "num_shards": shard_idx,
        "total_chunks": total_chunks,
        "built_at": _now(),
        "elapsed_seconds": round(time.perf_counter() - started, 1),
        **sig,
    }
    _write_json(out / MANIFEST_NAME, manifest)
    _write_json(out / PROGRESS_NAME, manifest)
    return manifest


class ShardedBM25Index:
    """分片 BM25 查询：逐片加载评分、合并全局 top_k（低内存）。"""

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        manifest = _read_json(self.cache_dir / MANIFEST_NAME)
        if not manifest or manifest.get("format") != FORMAT:
            raise ValueError(f"not a sharded BM25 cache: {self.cache_dir}")
        if manifest.get("status") not in ("completed", "already_completed"):
            raise ValueError(f"sharded BM25 not completed: {self.cache_dir}")
        self.manifest = manifest
        self._shard_files = sorted(self.cache_dir.glob(f"{SHARD_PREFIX}*.pkl"))
        if not self._shard_files:
            raise FileNotFoundError(f"no shard files under {self.cache_dir}")

    @property
    def size(self) -> int:
        return int(self.manifest.get("total_chunks", 0))

    @property
    def num_shards(self) -> int:
        return len(self._shard_files)

    @staticmethod
    def is_sharded(cache_dir: str | Path) -> bool:
        manifest = _read_json(Path(cache_dir) / MANIFEST_NAME)
        return bool(manifest and manifest.get("format") == FORMAT)

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        if not query_tokens or top_k <= 0:
            return []

        collected: list[tuple[float, dict[str, Any]]] = []
        for shard_file in self._shard_files:
            with open(shard_file, "rb") as f:
                payload = pickle.load(f)
            bm25 = payload["bm25"]
            chunks = payload["chunks"]
            scores = bm25.get_scores(query_tokens)

            k = min(top_k, len(scores))
            for idx in heapq.nlargest(k, range(len(scores)), key=scores.__getitem__):
                score = float(scores[idx])
                if score <= 0:
                    continue
                chunk = chunks[idx]
                collected.append(
                    (
                        score,
                        {
                            "chunk_id": chunk["chunk_id"],
                            "doc_id": chunk.get("doc_id"),
                            "source_title": chunk.get("source_title"),
                            "text": chunk.get("text"),
                            "chunk_index": chunk.get("chunk_index"),
                            "total_chunks": chunk.get("total_chunks"),
                            "token_count": chunk.get("token_count"),
                            "strategy": chunk.get("strategy"),
                            "source": "bm25",
                            "score": score,
                        },
                    )
                )
            del payload, bm25, chunks, scores

        collected.sort(key=lambda x: x[0], reverse=True)
        results: list[dict[str, Any]] = []
        for rank_idx, (_, item) in enumerate(collected[:top_k], start=1):
            item["rank"] = rank_idx
            results.append(item)
        return results


def cache_progress(out_dir: str | Path) -> dict[str, Any]:
    """读取分片索引状态（供 CLI/notebook 展示）。"""
    out = Path(out_dir)
    manifest = _read_json(out / MANIFEST_NAME)
    progress = _read_json(out / PROGRESS_NAME)
    shard_files = sorted(out.glob(f"{SHARD_PREFIX}*.pkl"))
    completed = bool(manifest and manifest.get("status") in ("completed", "already_completed"))
    return {
        "cache_dir": str(out),
        "completed": completed,
        "num_shard_files": len(shard_files),
        "manifest": manifest,
        "progress": progress,
    }
