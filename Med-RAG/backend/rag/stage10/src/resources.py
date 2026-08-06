"""Full-corpus resource checks for stage 10 (C0.5 / CLI).

Reuses 06 ``resolve_*`` after bootstrap; also verifies BM25 shard manifest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def check_full_corpus_resources(root: Path | None = None) -> dict[str, Any]:
    """Verify D: full Chroma / chunks / BM25 shards (and optional slim).

    ``ready`` is True only when required full-RAG assets exist:
    chroma_db_full, oa_comm_chunks.jsonl, bm25_full manifest completed.
    slim is optional (needed only for FormatChecker strict / year backfill).
    """
    from bootstrap import bootstrap_paths

    paths = bootstrap_paths(root)
    # Load 06 config by path so it does not clash with stage10 ``config``.
    import importlib.util

    cfg06_path = paths["stage06"] / "src" / "config.py"
    spec = importlib.util.spec_from_file_location("stage06_config", cfg06_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load stage06 config: {cfg06_path}")
    stage06_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage06_config)

    chunks = stage06_config.resolve_chunks_path("full")
    chroma_dir, collection = stage06_config.resolve_chroma("full")
    slim = stage06_config.resolve_slim_path()
    bm25_dir = stage06_config.resolve_bm25_cache_dir("full")

    bm25_manifest: dict[str, Any] | None = None
    bm25_ok = False
    if bm25_dir is not None:
        manifest_path = bm25_dir / "manifest.json"
        if manifest_path.is_file():
            try:
                bm25_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                bm25_ok = bm25_manifest.get("format") == "bm25_sharded_v1" and bm25_manifest.get(
                    "status"
                ) in ("completed", "already_completed")
            except (ValueError, OSError):
                bm25_manifest = None

    required_ok = chunks.is_file() and chroma_dir.is_dir() and bm25_ok
    return {
        "mode": "full",
        "chunks_path": str(chunks),
        "chunks_exists": chunks.is_file(),
        "chunks_size_gb": round(chunks.stat().st_size / (1024**3), 2) if chunks.is_file() else None,
        "chroma_persist_dir": str(chroma_dir),
        "chroma_exists": chroma_dir.is_dir(),
        "collection": collection,
        "bm25_cache_dir": str(bm25_dir) if bm25_dir else None,
        "bm25_ok": bm25_ok,
        "bm25_manifest": {
            "format": (bm25_manifest or {}).get("format"),
            "status": (bm25_manifest or {}).get("status"),
            "num_shards": (bm25_manifest or {}).get("num_shards"),
            "total_chunks": (bm25_manifest or {}).get("total_chunks"),
        }
        if bm25_manifest
        else None,
        "slim_path": str(slim),
        "slim_exists": slim.is_file(),
        "ready": required_ok,
        "status": "ready" if required_ok else "missing_resources",
    }


def probe_ollama(*, timeout: float = 5.0) -> dict[str, Any]:
    """Optional Ollama health check (live stages only)."""
    try:
        import httpx
    except ImportError:
        return {"ok": False, "error": "httpx_not_installed"}

    base_url = "http://127.0.0.1:11434"
    model = "deepseek-r1:7b"
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=timeout)
        ok = response.status_code == 200
        models: list[str] = []
        if ok:
            models = [str(item.get("name", "")) for item in response.json().get("models", [])]
        model_available = model in models or any(model.split(":")[0] in m for m in models)
        return {
            "ok": ok,
            "base_url": base_url,
            "model_requested": model,
            "model_available": model_available,
            "models_preview": models[:8],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "base_url": base_url,
            "model_requested": model,
            "model_available": False,
            "error": str(exc),
        }


def load_medical_abbrev(stage10: Path) -> dict[str, str]:
    """Load ``data/medical_abbrev.json`` → abbrev→expansion map."""
    path = stage10 / "data" / "medical_abbrev.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    abbrevs = payload.get("abbreviations", payload)
    if not isinstance(abbrevs, dict):
        raise ValueError(f"Invalid medical_abbrev.json structure: {path}")
    return {str(k): str(v) for k, v in abbrevs.items()}
