"""CLI 评测入口（阶段 4 实现；阶段 0 仅校验环境与路径）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STAGE06 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE06 / "src"))

from config import (  # noqa: E402
    DEFAULT_FUSION_STRATEGY,
    EMBED_MODEL,
    RERANK_MODEL,
    resolve_chroma,
    resolve_chunks_path,
    resolve_slim_path,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="06 检索流水线评测（骨架）")
    parser.add_argument(
        "--mode",
        choices=("sample", "full"),
        default="sample",
        help="sample=验证样本；full=全量库",
    )
    args = parser.parse_args()

    chunks = resolve_chunks_path(args.mode)
    chroma_dir, collection = resolve_chroma(args.mode)
    slim = resolve_slim_path()
    info = {
        "mode": args.mode,
        "chunks_path": str(chunks),
        "chunks_exists": chunks.is_file(),
        "slim_path": str(slim),
        "slim_exists": slim.is_file(),
        "chroma_persist_dir": str(chroma_dir),
        "chroma_exists": chroma_dir.is_dir(),
        "collection": collection,
        "embed_model": EMBED_MODEL,
        "rerank_model": RERANK_MODEL,
        "fusion_default": DEFAULT_FUSION_STRATEGY,
        "status": "skeleton",
    }
    print(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
