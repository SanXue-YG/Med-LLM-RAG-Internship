"""Ops statistics aggregation (QA JSONL / index / component health)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from app.config import DEFAULT_CONFIG, Stage12Config
from app.schemas.stats import ComponentHealth, HealthStats, IndexStats, QAStats

Mode = Literal["sample", "full"]


def aggregate_qa_stats(path: Path | str | None) -> QAStats:
    """Parse ``qa_calls.jsonl`` (same file ``QACallLogger`` writes).

    - ``status == "ok"`` → success; ``"error"`` → failure; other/missing → failure
    - ``avg_latency_seconds`` = mean(``latency_ms``) / 1000
    - missing / empty / all-blank file → zeros (``success_rate=0``, ``avg=0``)
    - malformed JSON lines are skipped (not counted)
    """
    total = 0
    success = 0
    failure = 0
    latency_sum = 0.0
    latency_n = 0

    if path is None:
        return QAStats(
            total_calls=0,
            success_count=0,
            failure_count=0,
            success_rate=0.0,
            avg_latency_seconds=0.0,
        )

    p = Path(path)
    if not p.is_file():
        return QAStats(
            total_calls=0,
            success_count=0,
            failure_count=0,
            success_rate=0.0,
            avg_latency_seconds=0.0,
        )

    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            total += 1
            if row.get("status") == "ok":
                success += 1
            else:
                failure += 1
            lat = row.get("latency_ms")
            if isinstance(lat, (int, float)):
                latency_sum += float(lat)
                latency_n += 1

    rate = (success / total) if total else 0.0
    avg_s = (latency_sum / latency_n / 1000.0) if latency_n else 0.0
    return QAStats(
        total_calls=total,
        success_count=success,
        failure_count=failure,
        success_rate=round(rate, 6),
        avg_latency_seconds=round(avg_s, 6),
    )


def _dir_size_bytes(path: Path) -> int | None:
    if not path.is_dir():
        return None
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _chroma_paths(mode: Mode) -> tuple[Path, str]:
    from dataset_paths import (  # type: ignore
        CHROMA_FULL_DIR,
        CHROMA_SAMPLE_DIR,
        COLLECTION_FULL,
        COLLECTION_SAMPLE,
    )

    if mode == "full":
        return Path(CHROMA_FULL_DIR), COLLECTION_FULL
    return Path(CHROMA_SAMPLE_DIR), COLLECTION_SAMPLE


def _chroma_count(persist: Path, collection: str) -> int | None:
    if not persist.is_dir():
        return None
    try:
        import chromadb  # type: ignore

        client = chromadb.PersistentClient(path=str(persist))
        return int(client.get_collection(collection).count())
    except Exception:  # noqa: BLE001 — ops endpoint must not crash
        return None


def _bm25_num_shards(mode: Mode) -> int | None:
    if mode != "full":
        return None
    try:
        from dataset_paths import BM25_FULL_DIR  # type: ignore
    except ImportError:
        return None
    manifest_path = Path(BM25_FULL_DIR) / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        n = data.get("num_shards")
        return int(n) if n is not None else None
    except Exception:  # noqa: BLE001
        return None


def collect_index_stats(
    retrieval_mode: Mode | None = None,
    documents_mode: Mode | None = None,
    *,
    config: Stage12Config | None = None,
) -> IndexStats:
    """Chroma chunk scale + documents sqlite row count (never confuse the two)."""
    cfg = config or DEFAULT_CONFIG
    r_mode: Mode = retrieval_mode or cfg.retrieval_mode  # type: ignore[assignment]
    d_mode: Mode = documents_mode or cfg.documents_mode  # type: ignore[assignment]

    persist, collection = _chroma_paths(r_mode)
    chunk_count = _chroma_count(persist, collection)
    index_size = _dir_size_bytes(persist)

    document_count: int | None = None
    try:
        from app.documents_index import status as documents_status

        st = documents_status(d_mode)
        document_count = st.get("row_count")
    except Exception:  # noqa: BLE001
        document_count = None

    note_parts = [
        "incremental_update_count is MVP placeholder (always 0)",
        "document_count = documents sqlite rows; chunk_count = Chroma collection",
    ]
    return IndexStats(
        document_count=document_count,
        chunk_count=chunk_count,
        index_size_bytes=index_size,
        incremental_update_count=0,
        note="; ".join(note_parts),
        retrieval_mode=r_mode,
        documents_mode=d_mode,
        bm25_num_shards=_bm25_num_shards(r_mode),
    )


def collect_component_health(
    *,
    retrieval_mode: Mode | None = None,
    config: Stage12Config | None = None,
) -> HealthStats:
    """LLM (probe_ollama) + vector persist/count + database=skipped + api=ok."""
    from app.bridge11 import load_stage11

    cfg = config or DEFAULT_CONFIG
    mode: Mode = retrieval_mode or cfg.retrieval_mode  # type: ignore[assignment]
    s11 = load_stage11()

    ollama: dict[str, Any] = s11["probe_ollama"]()
    if ollama.get("ok") and ollama.get("model_present"):
        llm_status: Literal["ok", "degraded", "down", "skipped"] = "ok"
    elif ollama.get("ok"):
        llm_status = "degraded"
    else:
        llm_status = "down"

    persist, collection = _chroma_paths(mode)
    chunk_count = _chroma_count(persist, collection)
    vector_detail: dict[str, Any] = {
        "retrieval_mode": mode,
        "persist_dir": str(persist),
        "persist_exists": persist.is_dir(),
        "collection": collection,
        "chunk_count": chunk_count,
    }
    if mode == "full":
        try:
            full_probe = s11["probe_full_dataset"](check_chroma_collection=False)
            vector_detail["full_dataset"] = {
                "ready": full_probe.get("ready"),
                "chroma_full_exists": full_probe.get("chroma_full_exists"),
                "bm25_manifest_ok": full_probe.get("bm25_manifest_ok"),
                "bm25_num_shards": full_probe.get("bm25_num_shards"),
            }
        except Exception as exc:  # noqa: BLE001
            vector_detail["full_dataset_error"] = f"{type(exc).__name__}: {exc}"

    if persist.is_dir() and chunk_count is not None:
        vector_status: Literal["ok", "degraded", "down", "skipped"] = "ok"
    elif persist.is_dir():
        vector_status = "degraded"
    else:
        vector_status = "down"

    components = [
        ComponentHealth(name="llm", status=llm_status, detail=ollama),
        ComponentHealth(name="vector_db", status=vector_status, detail=vector_detail),
        ComponentHealth(
            name="database",
            status="skipped",
            detail={
                "reason": "no relational DB; QA ops log is JSONL (qa_calls.jsonl)",
            },
        ),
        ComponentHealth(
            name="api",
            status="ok",
            detail={"stage": "12-2", "service": "medical-rag-api"},
        ),
    ]
    return HealthStats(components=components)
