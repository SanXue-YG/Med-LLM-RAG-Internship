"""Build full-corpus BM25 index (sharded, low-memory) for stage 06/09 reuse.

Default output: 09 .../data/bm25_full  (local D:; E: is manual backup only)

Examples:
    # 查看状态 / 断点进度
    python scripts/build_bm25_full_index.py --status

    # 分片构建（默认，断点续建）；死机时可调小 --shard-size
    python scripts/build_bm25_full_index.py --shard-size 100000

    # smoke（只建前 10 万条）
    python scripts/build_bm25_full_index.py --limit 100000 --shard-size 50000

    # 从头重建（忽略已有进度）
    python scripts/build_bm25_full_index.py --no-resume
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build full BM25 offline index (stage 09, sharded).")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: 09 .../data/bm25_full)",
    )
    parser.add_argument(
        "--shard-size",
        type=int,
        default=200_000,
        help="Chunks per shard (smaller = lower memory peak). Default 200000.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Smoke: only first N chunks")
    parser.add_argument("--no-resume", action="store_true", help="Rebuild from scratch")
    parser.add_argument("--status", action="store_true", help="Only show build status/progress")
    parser.add_argument("--check-only", action="store_true", help="Alias of --status")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    stage09 = script_path.parents[1]
    stage06 = stage09.parent / "06 检索系统开发第二部分"
    sys.path.insert(0, str(stage09 / "src"))

    from bm25_store import (
        build_sharded_full_bm25,
        resolve_bm25_full_cache_dir,
        sharded_status,
    )

    out = args.output or resolve_bm25_full_cache_dir()

    if args.status or args.check_only:
        info = sharded_status(stage06, output_dir=out)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return

    print(f"[bm25-full] sharded build -> {out}")
    print(f"[bm25-full] shard_size={args.shard_size} resume={not args.no_resume}")
    if args.limit:
        print(f"[bm25-full] limit={args.limit} (smoke mode)")

    manifest = build_sharded_full_bm25(
        stage06,
        output_dir=out,
        shard_size=args.shard_size,
        resume=not args.no_resume,
        limit=args.limit,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    status = manifest.get("status")
    if status == "already_completed":
        print("[OK] already completed (no rebuild).")
    else:
        print(
            f"[OK] status={status} num_shards={manifest.get('num_shards')} "
            f"total_chunks={manifest.get('total_chunks')} "
            f"elapsed={manifest.get('elapsed_seconds')}s"
        )


if __name__ == "__main__":
    main()
