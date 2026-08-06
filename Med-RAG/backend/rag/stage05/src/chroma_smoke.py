"""Chroma smoke test 与 HNSW bin 磁盘探测（05 联调用）。"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

HNSW_BIN_MARKERS = ("data_level0.bin", "link_lists.bin", "length.bin")


def detect_hnsw_bins(persist_dir: str | Path) -> dict[str, Any]:
    """检查 persist 目录下 HNSW 段是否含完整 bin 文件。"""
    persist_dir = Path(persist_dir)
    db = persist_dir / "chroma.sqlite3"
    if not db.is_file():
        return {"persist_dir": str(persist_dir), "segments": [], "any_complete_hnsw": False}

    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT id FROM segments WHERE type LIKE '%hnsw%'"
        ).fetchall()
    finally:
        con.close()

    segments: list[dict[str, Any]] = []
    any_complete = False
    for (seg_id,) in rows:
        seg_dir = persist_dir / seg_id
        bins = {name: (seg_dir / name).is_file() for name in HNSW_BIN_MARKERS}
        complete = all(bins.values())
        any_complete = any_complete or complete
        total_bin_bytes = sum(
            (seg_dir / n).stat().st_size for n in HNSW_BIN_MARKERS if (seg_dir / n).is_file()
        )
        segments.append(
            {
                "segment_id": seg_id,
                "dir_exists": seg_dir.is_dir(),
                "bins": bins,
                "complete_hnsw": complete,
                "bin_bytes": total_bin_bytes,
            }
        )

    return {
        "persist_dir": str(persist_dir.resolve()),
        "segments": segments,
        "any_complete_hnsw": any_complete,
    }


def timed_queries(
    builder: Any,
    query_text: str,
    *,
    n_results: int = 5,
    where_filter: dict | None = None,
    repeats: int = 3,
    warmup: int = 1,
) -> dict[str, Any]:
    """对同一 query 重复计时（秒）。"""
    for _ in range(warmup):
        builder.query(query_text, n_results=n_results, where_filter=where_filter)

    times: list[float] = []
    last_ids: list[str] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        res = builder.query(query_text, n_results=n_results, where_filter=where_filter)
        times.append(time.perf_counter() - t0)
        last_ids = list(res["ids"][0])

    return {
        "query": query_text,
        "n_results": n_results,
        "where_filter": where_filter,
        "repeats": repeats,
        "times_sec": [round(t, 4) for t in times],
        "mean_sec": round(sum(times) / len(times), 4),
        "top_ids": last_ids,
    }
