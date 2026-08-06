"""Lightweight probes for notebook C0.5 / future ``/health`` (no full pipeline load)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

from app.config import DEFAULT_CONFIG, MED_RAG_HOME, MedRagConfig as Stage11Config


def probe_ollama(config: Stage11Config | None = None, *, timeout: float = 5.0) -> dict[str, Any]:
    """HTTP probe against Ollama ``/api/tags`` (does not load Chroma/BM25)."""
    cfg = config or DEFAULT_CONFIG
    url = cfg.ollama_base_url.rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
        models = [m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)]
        wanted = cfg.ollama_model
        return {
            "ok": True,
            "base_url": cfg.ollama_base_url,
            "model_configured": wanted,
            "model_present": any(wanted in (n or "") for n in models),
            "models_sample": models[:8],
        }
    except Exception as exc:  # noqa: BLE001 — probe must never raise to callers
        return {
            "ok": False,
            "base_url": cfg.ollama_base_url,
            "model_configured": cfg.ollama_model,
            "error": f"{type(exc).__name__}: {exc}",
        }


def try_import_stage10() -> dict[str, Any]:
    """Confirm stage-10 constrained pipeline module is importable after bootstrap."""
    try:
        from constrained_pipeline import ConstrainedGenerationPipeline  # type: ignore

        return {
            "ok": True,
            "class": ConstrainedGenerationPipeline.__name__,
            "module": ConstrainedGenerationPipeline.__module__,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def probe_full_dataset(*, check_chroma_collection: bool = False) -> dict[str, Any]:
    """Filesystem readiness for ``retrieval_mode=full`` (no pipeline cold-start)."""
    repo_root = MED_RAG_HOME
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    backend = MED_RAG_HOME / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from paths import (  # type: ignore
        BM25_FULL_DIR,
        CHROMA_FULL_DIR,
        CHUNKS_FULL_JSONL,
        COLLECTION_FULL,
        DATASET_ROOT,
        SLIM_JSONL,
    )

    manifest_path = Path(BM25_FULL_DIR) / "manifest.json"
    manifest: dict[str, Any] = {}
    manifest_ok = False
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_ok = (
                manifest.get("format") == "bm25_sharded_v1"
                and manifest.get("status") == "completed"
                and int(manifest.get("num_shards") or 0) >= 1
            )
        except Exception as exc:  # noqa: BLE001
            manifest = {"error": f"{type(exc).__name__}: {exc}"}

    chroma_ok = Path(CHROMA_FULL_DIR).is_dir()
    chunks_ok = Path(CHUNKS_FULL_JSONL).is_file()
    slim_ok = Path(SLIM_JSONL).is_file()

    collection_ok: bool | None = None
    collection_detail: str | None = None
    if check_chroma_collection and chroma_ok:
        try:
            import chromadb  # type: ignore

            client = chromadb.PersistentClient(path=str(CHROMA_FULL_DIR))
            names = [c.name for c in client.list_collections()]
            collection_ok = COLLECTION_FULL in names
            collection_detail = ",".join(names[:12])
        except Exception as exc:  # noqa: BLE001
            collection_ok = False
            collection_detail = f"{type(exc).__name__}: {exc}"

    ollama = probe_ollama()
    ready = bool(chroma_ok and manifest_ok and ollama.get("ok") and ollama.get("model_present"))
    if check_chroma_collection and collection_ok is False:
        ready = False

    return {
        "ready": ready,
        "dataset_root": str(DATASET_ROOT),
        "chroma_full_dir": str(CHROMA_FULL_DIR),
        "chroma_full_exists": chroma_ok,
        "collection_expected": COLLECTION_FULL,
        "collection_ok": collection_ok,
        "collection_detail": collection_detail,
        "bm25_full_dir": str(BM25_FULL_DIR),
        "bm25_manifest_ok": manifest_ok,
        "bm25_num_shards": manifest.get("num_shards"),
        "bm25_total_chunks": manifest.get("total_chunks"),
        "bm25_status": manifest.get("status"),
        "chunks_jsonl_exists": chunks_ok,
        "chunks_jsonl": str(CHUNKS_FULL_JSONL),
        "slim_jsonl_exists": slim_ok,
        "ollama": ollama,
        "hints": [
            "Set RUN_LIVE_FULL=True only after ready=True",
            "Expect multi-minute cold start (Chroma+BM25+reranker+Ollama)",
            "Keep a single RagService singleton — do not from_mode(full) per request",
        ],
    }
