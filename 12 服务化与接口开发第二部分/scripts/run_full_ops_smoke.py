"""CLI: stage-12 full Dataset ops smoke (writes outputs/reports/full_ops_smoke*).

Usage (from stage-12 dir, med-rag-verify)::

    python scripts/run_full_ops_smoke.py
    python scripts/run_full_ops_smoke.py --check-only
    python scripts/run_full_ops_smoke.py --no-stream
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STAGE12 = Path(__file__).resolve().parents[1]
REPO = STAGE12.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 12 full ops live smoke")
    parser.add_argument("--query", default="metformin cardiovascular effects")
    parser.add_argument("--follow-up", default="follow-up: what is the evidence strength?")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--check-collection", action="store_true")
    parser.add_argument("--check-only", action="store_true", help="probe readiness only")
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="default: <stage12>/outputs/reports",
    )
    args = parser.parse_args()

    for p in (str(REPO), str(STAGE12)):
        if p not in sys.path:
            sys.path.insert(0, p)

    report_dir = Path(args.report_dir) if args.report_dir else (STAGE12 / "outputs" / "reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    # Env MUST be set before importing app.config / app.main
    from app.full_ops_smoke import apply_full_env, probe_full_ops_environment, run_full_ops_smoke

    applied = apply_full_env(log_dir=report_dir)
    print("env", json.dumps(applied, ensure_ascii=False))

    from app.bootstrap import bootstrap_paths
    from app.bridge11 import reset_stage11_cache

    reset_stage11_cache()
    bootstrap_paths(STAGE12)

    if args.check_only:
        readiness = probe_full_ops_environment(
            check_chroma_collection=args.check_collection
        )
        print(json.dumps({
            "ready": readiness.get("ready"),
            "documents_full_ok": readiness.get("documents_full_ok"),
            "bm25_manifest_ok": readiness.get("bm25_manifest_ok"),
            "chroma_full_exists": readiness.get("chroma_full_exists"),
            "bm25_total_chunks": readiness.get("bm25_total_chunks"),
            "documents_row_count": (readiness.get("documents_full") or {}).get("row_count"),
            "ollama": readiness.get("ollama"),
        }, ensure_ascii=False, indent=2))
        return 0 if readiness.get("ready") else 1

    record = run_full_ops_smoke(
        query=args.query,
        follow_up=args.follow_up,
        top_k=args.top_k,
        run_stream=not args.no_stream,
        http_timeout=args.timeout,
        report_dir=report_dir,
        check_chroma_collection=args.check_collection,
    )
    summary = {
        "ok": record.get("ok"),
        "error": record.get("error"),
        "warmup_sec": record.get("warmup_sec"),
        "checks": record.get("checks"),
        "artifacts": record.get("artifacts"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if record.get("qa_turn1"):
        s = record["qa_turn1"]
        print(
            f"qa1 wall={s.get('wall_clock_sec')}s sources={s.get('n_sources')} "
            f"citation_ok={s.get('citation_ok')} pmcids={s.get('pmcids')}"
        )
    if record.get("qa_turn2"):
        s = record["qa_turn2"]
        print(f"qa2 wall={s.get('wall_clock_sec')}s sources={s.get('n_sources')}")
    return 0 if record.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
