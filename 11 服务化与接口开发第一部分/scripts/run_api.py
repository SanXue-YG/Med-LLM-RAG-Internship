"""Start the stage-11 FastAPI app with uvicorn.

Usage (from repo root or stage 11 dir)::

    python "11 服务化与接口开发第一部分/scripts/run_api.py"
    python "11 服务化与接口开发第一部分/scripts/run_api.py" --no-reload
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

STAGE11 = Path(__file__).resolve().parents[1]
if str(STAGE11) not in sys.path:
    sys.path.insert(0, str(STAGE11))

from app.bootstrap import bootstrap_paths  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402


def main() -> None:
    bootstrap_paths(STAGE11)
    parser = argparse.ArgumentParser(description="Run Medical RAG FastAPI (stage 11)")
    parser.add_argument("--host", default=DEFAULT_CONFIG.host)
    parser.add_argument("--port", type=int, default=DEFAULT_CONFIG.port)
    parser.add_argument(
        "--reload",
        dest="reload",
        action="store_true",
        default=True,
        help="auto-reload on code change (default: on)",
    )
    parser.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="disable auto-reload",
    )
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(STAGE11)] if args.reload else None,
    )


if __name__ == "__main__":
    main()
