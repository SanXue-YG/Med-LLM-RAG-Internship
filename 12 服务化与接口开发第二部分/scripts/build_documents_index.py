"""CLI: build documents_{sample,full}.sqlite (batch upsert + resume).

Examples::

    python scripts/build_documents_index.py --mode sample
    python scripts/build_documents_index.py --mode full --batch-size 50000
    python scripts/build_documents_index.py --mode full --status
    python scripts/build_documents_index.py --mode full --no-resume
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STAGE12 = Path(__file__).resolve().parents[1]
REPO = STAGE12.parent
for p in (STAGE12, REPO):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from app.bootstrap import bootstrap_paths  # noqa: E402
from app.documents_index import build_documents_index, status  # noqa: E402


def main() -> None:
    bootstrap_paths(STAGE12)
    parser = argparse.ArgumentParser(description="Build Dataset/documents sqlite index")
    parser.add_argument("--mode", choices=("sample", "full"), default="sample")
    parser.add_argument("--batch-size", type=int, default=50_000)
    parser.add_argument("--limit", type=int, default=None, help="Smoke: stop after N upserts")
    parser.add_argument(
        "--resume",
        dest="resume",
        action="store_true",
        default=True,
        help="Resume from progress_{mode}.json (default)",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Rebuild from scratch",
    )
    parser.add_argument("--status", action="store_true", help="Print status and exit")
    args = parser.parse_args()

    if args.status:
        info = status(args.mode)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return

    def _cb(payload: dict) -> None:
        phase = payload.get("phase", "")
        print(
            f"[documents-index] mode={args.mode} phase={phase} "
            f"lines={payload.get('processed_lines')} "
            f"rows={payload.get('valid_rows')} "
            f"matched={payload.get('matched_sample')}/"
            f"{payload.get('sample_target')} "
            f"last={payload.get('last_pmcid')}",
            flush=True,
        )

    print(
        f"[documents-index] build mode={args.mode} batch_size={args.batch_size} "
        f"resume={args.resume} limit={args.limit}",
        flush=True,
    )
    manifest = build_documents_index(
        args.mode,
        batch_size=args.batch_size,
        resume=args.resume,
        limit=args.limit,
        progress_cb=_cb,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    print(f"[OK] status={manifest.get('status')} row_count={manifest.get('row_count')}")


if __name__ == "__main__":
    main()
