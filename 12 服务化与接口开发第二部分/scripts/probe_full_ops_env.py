"""CLI: probe full-ops prerequisites (documents/chroma/bm25/ollama).

Run in a **fresh process** from Jupyter to avoid WinError 6714.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    STAGE12 = Path(__file__).resolve().parents[1]
except OSError:
    STAGE12 = Path(os.path.abspath(__file__)).parents[1]
if str(STAGE12) not in sys.path:
    sys.path.insert(0, str(STAGE12))

from app.full_ops_smoke import apply_full_env, probe_full_ops_environment  # noqa: E402


def main() -> int:
    report_dir = STAGE12 / "outputs" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    applied = apply_full_env(log_dir=report_dir)
    ready = probe_full_ops_environment(check_chroma_collection=False)
    out = {
        "env": applied,
        "ready": ready.get("ready"),
        "documents_full_ok": ready.get("documents_full_ok"),
        "documents_full": {
            k: (ready.get("documents_full") or {}).get(k)
            for k in ("completed", "row_count", "sqlite_exists")
        },
        "chroma_full_exists": ready.get("chroma_full_exists"),
        "bm25_manifest_ok": ready.get("bm25_manifest_ok"),
        "bm25_total_chunks": ready.get("bm25_total_chunks"),
        "ollama_ok": (ready.get("ollama") or {}).get("ok"),
        "model_present": (ready.get("ollama") or {}).get("model_present"),
        "hints": ready.get("hints"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ready.get("ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
