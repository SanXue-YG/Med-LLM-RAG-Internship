"""CLI: stage 4.5 full-corpus HTTP smoke (writes outputs/reports/).

Usage (from stage-11 dir, med-rag-verify)::

    python scripts/run_full_api_smoke.py
    python scripts/run_full_api_smoke.py --no-stream
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STAGE11 = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 11 full live API smoke")
    parser.add_argument("--query", default="metformin cardiovascular effects")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--check-collection", action="store_true")
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()

    sys.path.insert(0, str(STAGE11))
    from app.bootstrap import bootstrap_paths

    bootstrap_paths(STAGE11)

    from app.full_smoke import run_full_http_smoke

    record = run_full_http_smoke(
        query=args.query,
        top_k=args.top_k,
        run_stream=not args.no_stream,
        http_timeout=args.timeout,
        check_chroma_collection=args.check_collection,
    )
    print(json.dumps({k: record.get(k) for k in ("ok", "error", "warmup_sec", "artifacts")}, indent=2))
    if record.get("sync"):
        s = record["sync"]
        print(
            f"sync wall={s.get('wall_clock_sec')}s "
            f"pipeline={s.get('pipeline_total_time_seconds')}s "
            f"sources={s.get('n_sources')} "
            f"citation_ok={s.get('citation_ok')}"
        )
    return 0 if record.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
