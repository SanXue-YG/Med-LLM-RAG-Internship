"""Start Med-RAG FastAPI (unified QA + ops + ingest).

Usage::

    cd Med-RAG
    python backend/scripts/run_api.py --no-reload
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
HOME = BACKEND.parent
for p in (str(BACKEND), str(HOME)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.bootstrap import bootstrap_paths  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402


def main() -> None:
    bootstrap_paths(HOME)
    parser = argparse.ArgumentParser(description="Run Med-RAG FastAPI")
    parser.add_argument("--host", default=DEFAULT_CONFIG.host)
    parser.add_argument("--port", type=int, default=DEFAULT_CONFIG.port)
    parser.add_argument(
        "--reload",
        dest="reload",
        action="store_true",
        default=False,
        help="auto-reload on code change",
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="disable auto-reload (default)",
    )
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(BACKEND)] if args.reload else None,
    )


if __name__ == "__main__":
    main()
