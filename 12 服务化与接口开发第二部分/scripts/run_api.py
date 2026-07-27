"""Start stage-12 FastAPI (ops shell + stage-11 health/qa).

Usage::

    python "12 服务化与接口开发第二部分/scripts/run_api.py"
    python "12 服务化与接口开发第二部分/scripts/run_api.py" --no-reload
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

STAGE12 = Path(__file__).resolve().parents[1]
REPO = STAGE12.parent
for p in (STAGE12, REPO):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from app.bootstrap import bootstrap_paths  # noqa: E402
from app.config import DEFAULT_CONFIG  # noqa: E402


def main() -> None:
    bootstrap_paths(STAGE12)
    parser = argparse.ArgumentParser(description="Run Medical RAG FastAPI (stage 12)")
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
        reload_dirs=[str(STAGE12), str(STAGE12.parent / "11 服务化与接口开发第一部分")]
        if args.reload
        else None,
    )


if __name__ == "__main__":
    main()
