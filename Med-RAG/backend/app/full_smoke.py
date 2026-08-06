"""Stage 4.5 — full-corpus + Ollama smoke helpers (report artifacts).

Primary path runs ``RagService.answer`` on the **main thread**. On some Windows
setups (Chinese paths / cloud-synced folders), Starlette's sync-route threadpool
raises ``WinError 6714`` while importing/loading transformers — HTTP is still
attempted after a main-thread warm, but main-thread success is enough for 4.5.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import STAGE11_DIR, Stage11Config
from app.core.logging import get_logger
from app.deps import get_qa_logger, get_rag_service, get_session_store, reset_singletons
from app.probe import probe_full_dataset
from app.services.qa_logger import QACallLogger
from app.services.rag_service import RagService
from app.services.session_store import MemorySessionStore, SessionTurn
from app.services.sse_pseudo import iter_pseudo_tokens

logger = get_logger("full_smoke")

DEFAULT_QUERY = "metformin cardiovascular effects"
REPORT_DIR = STAGE11_DIR / "outputs" / "reports"


def parse_sse(raw: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in [b for b in raw.split("\n\n") if b.strip()]:
        name, data_lines = "message", []
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        payload: dict[str, Any] = {}
        if data_lines:
            payload = json.loads("\n".join(data_lines))
        events.append((name, payload))
    return events


def _summarize_result(result: dict[str, Any], *, wall_sec: float, request_id: str | None = None) -> dict[str, Any]:
    metrics = result.get("generation_metrics") or {}
    checks = result.get("constraint_checks") or {}
    sources = result.get("sources") or []
    return {
        "request_id": request_id,
        "wall_clock_sec": round(wall_sec, 2),
        "pipeline_total_time_seconds": metrics.get("total_time_seconds"),
        "stage_times": metrics.get("stage_times"),
        "n_sources": len(sources),
        "source_ids": [
            s.get("chunk_id") or s.get("doc_id") or s.get("index") for s in sources[:8]
        ],
        "constraint_boundary_hit": checks.get("boundary_hit"),
        "citation_ok": (checks.get("citation") or {}).get("ok"),
        "format_ok": (checks.get("format") or {}).get("ok"),
        "retry_count": result.get("retry_count"),
        "repaired": result.get("repaired"),
        "top_k_applied": result.get("top_k_applied"),
        "top_k_mode": result.get("top_k_mode"),
        "answer_preview": (result.get("answer") or "")[:400],
        "answer_chars": len(result.get("answer") or ""),
    }


def _pseudo_stream_from_answer(answer: str, *, window: int = 32) -> dict[str, Any]:
    """Build pseudo-SSE event list without going through TestClient."""
    chunks = list(iter_pseudo_tokens(answer, window=window))
    names = ["meta", *(["token"] * len(chunks)), "done"]
    return {
        "stream_mode": "pseudo",
        "event_names": names,
        "n_token_events": len(chunks),
        "tokens_chars": sum(len(c) for c in chunks),
        "note": "pseudo-SSE reconstructed on main thread after full answer",
    }


def run_full_http_smoke(
    *,
    query: str = DEFAULT_QUERY,
    top_k: int = 5,
    run_stream: bool = True,
    http_timeout: float = 900.0,
    report_dir: Path | None = None,
    check_chroma_collection: bool = False,
    try_http_after_warm: bool = True,
) -> dict[str, Any]:
    """Full live smoke: readiness → main-thread answer → figures (+ optional HTTP)."""
    _ = http_timeout
    out_dir = Path(report_dir or REPORT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    readiness = probe_full_dataset(check_chroma_collection=check_chroma_collection)
    record: dict[str, Any] = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": "4.5-full-live",
        "query": query,
        "top_k": top_k,
        "retrieval_mode": "full",
        "pipeline_backend": "constrained10",
        "readiness": readiness,
        "path": "main_thread_rag_service",
        "sync": None,
        "stream": None,
        "http_probe": None,
        "warmup_sec": None,
        "ok": False,
        "error": None,
        "artifacts": {},
        "windows_note": (
            "If HTTP TestClient fails with WinError 6714 on Chinese/cloud paths, "
            "main-thread RagService.answer remains the authoritative full-live proof."
        ),
    }

    if not readiness.get("ready"):
        record["error"] = "full environment not ready — see readiness"
        _write_json(out_dir / "full_api_smoke.json", record)
        return record

    reset_singletons()
    cfg = Stage11Config(retrieval_mode="full", pipeline_backend="constrained10")
    store = MemorySessionStore(cfg)
    rag = RagService(cfg, inject_history=True)
    qlog = QACallLogger(cfg)
    qlog.path = out_dir / "qa_calls_full_smoke.jsonl"
    qlog.path.parent.mkdir(parents=True, exist_ok=True)
    if qlog.path.exists():
        qlog.path.unlink()

    try:
        t_warm = time.perf_counter()
        rag.ensure_pipeline()
        record["warmup_sec"] = round(time.perf_counter() - t_warm, 2)
        logger.info("full_pipeline_warmup_sec=%.1f", record["warmup_sec"])

        request_id = str(uuid.uuid4())
        t0 = time.perf_counter()
        result = rag.answer(query, top_k=top_k)
        wall = time.perf_counter() - t0

        answer = str(result.get("answer") or "")
        sources = list(result.get("sources") or [])
        rec_sess = store.create()
        sid = rec_sess.session_id
        store.append(
            sid,
            SessionTurn(
                query=query,
                answer=answer,
                meta={"top_k": top_k, "n_sources": len(sources), "full_smoke": True},
            ),
        )

        sync_summary = _summarize_result(result, wall_sec=wall, request_id=request_id)
        sync_summary["session_id"] = sid
        sync_summary["http_code"] = 0
        record["sync"] = sync_summary

        qlog.log(
            request_id=request_id,
            query=query,
            status="ok",
            latency_ms=wall * 1000,
            session_id=sid,
            code=0,
            top_k=top_k,
            n_sources=len(sources),
            extra={"stream_mode": None, "path": "main_thread", "retrieval_mode": "full"},
        )

        if run_stream:
            t1 = time.perf_counter()
            # Second turn with history prefix (same as /qa/stream business path).
            history = list(store.require(sid).turns)
            follow = "follow-up: evidence strength?"
            result2 = rag.answer(follow, top_k=top_k, session_history=history)
            stream_wall = time.perf_counter() - t1
            answer2 = str(result2.get("answer") or "")
            store.append(
                sid,
                SessionTurn(query=follow, answer=answer2, meta={"stream": True}),
            )
            pseudo = _pseudo_stream_from_answer(answer2, window=cfg.stream_chunk_chars)
            stream_summary = _summarize_result(result2, wall_sec=stream_wall)
            stream_summary.update(pseudo)
            stream_summary["session_id"] = sid
            record["stream"] = stream_summary
            qlog.log(
                request_id=str(uuid.uuid4()),
                query=follow,
                status="ok",
                latency_ms=stream_wall * 1000,
                session_id=sid,
                code=0,
                top_k=top_k,
                n_sources=len(result2.get("sources") or []),
                extra={"stream_mode": "pseudo", "path": "main_thread", "retrieval_mode": "full"},
            )

        if try_http_after_warm:
            record["http_probe"] = _try_http_after_warm(rag, store, qlog, query=query, top_k=top_k)

        record["ok"] = True
        record["session_turns"] = len(store.require(sid).turns)
        if qlog.path.is_file():
            record["qa_log_lines"] = len(
                qlog.path.read_text(encoding="utf-8").strip().splitlines()
            )

        figs = render_report_figures(record, out_dir)
        record["artifacts"] = {
            "json": str(out_dir / "full_api_smoke.json"),
            "qa_log": str(qlog.path),
            **figs,
        }
        _write_json(out_dir / "full_api_smoke.json", record)
        return record
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"{type(exc).__name__}: {exc}"
        logger.exception("full_http_smoke_failed")
        _write_json(out_dir / "full_api_smoke.json", record)
        return record
    finally:
        reset_singletons()


def _try_http_after_warm(
    rag: RagService,
    store: MemorySessionStore,
    qlog: QACallLogger,
    *,
    query: str,
    top_k: int,
) -> dict[str, Any]:
    """Optional HTTP probe after models are loaded on the main thread."""
    from fastapi.testclient import TestClient

    from app.main import app

    app.dependency_overrides[get_rag_service] = lambda: rag
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_qa_logger] = lambda: qlog
    try:
        client = TestClient(app, raise_server_exceptions=False)
        ready = client.get("/ready")
        # Short query reuses warm embedder/reranker; may still fail on WinError 6714.
        resp = client.post(
            "/api/v1/qa",
            json={"query": query[:80], "top_k": min(top_k, 3)},
        )
        body = resp.json() if resp.content else {}
        return {
            "ready_status": ready.status_code,
            "qa_status": resp.status_code,
            "qa_code": body.get("code"),
            "ok": resp.status_code == 200 and body.get("code") == 0,
            "message": body.get("message"),
            "error_type": (body.get("data") or {}).get("error_type")
            if isinstance(body.get("data"), dict)
            else None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        app.dependency_overrides.clear()


def render_report_figures(record: dict[str, Any], out_dir: Path) -> dict[str, str]:
    """Write PNG charts for stage-5 report; returns path map."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    sync = record.get("sync") or {}
    stage_times = sync.get("stage_times") or {}
    if stage_times:
        fig, ax = plt.subplots(figsize=(7.2, 3.8))
        labels = list(stage_times.keys())
        vals = [float(stage_times[k] or 0) for k in labels]
        colors = ["#2a6f97" if v > 0 else "#cbd5e1" for v in vals]
        ax.barh(labels, vals, color=colors)
        ax.set_xlabel("seconds")
        ax.set_title("Full live — generation stage_times (sync path)")
        ax.invert_yaxis()
        fig.tight_layout()
        p = out_dir / "full_api_smoke_stage_times.png"
        fig.savefig(p, dpi=140)
        plt.close(fig)
        paths["stage_times_png"] = str(p)

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    labels2: list[str] = []
    vals2: list[float] = []
    if record.get("warmup_sec") is not None:
        labels2.append("warmup\n(ensure_pipeline)")
        vals2.append(float(record["warmup_sec"]))
    if sync.get("wall_clock_sec") is not None:
        labels2.append("sync\nwall")
        vals2.append(float(sync["wall_clock_sec"]))
    if sync.get("pipeline_total_time_seconds") is not None:
        labels2.append("pipeline\ntotal")
        vals2.append(float(sync["pipeline_total_time_seconds"]))
    stream = record.get("stream") or {}
    if stream.get("wall_clock_sec") is not None:
        labels2.append("stream-turn\nwall")
        vals2.append(float(stream["wall_clock_sec"]))
    if labels2:
        ax.bar(labels2, vals2, color=["#1b4332", "#2a6f97", "#468faf", "#95d5b2"][: len(labels2)])
        ax.set_ylabel("seconds")
        ax.set_title("Full live — wall / pipeline timing overview")
        for i, v in enumerate(vals2):
            ax.text(i, v, f"{v:.1f}s", ha="center", va="bottom", fontsize=9)
        fig.tight_layout()
        p = out_dir / "full_api_smoke_overview.png"
        fig.savefig(p, dpi=140)
        plt.close(fig)
        paths["overview_png"] = str(p)

    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    flags = [
        ("citation_ok", bool(sync.get("citation_ok"))),
        ("format_ok", bool(sync.get("format_ok"))),
        ("boundary_hit", bool(sync.get("constraint_boundary_hit"))),
    ]
    ax.bar(
        [f[0] for f in flags],
        [1 if f[1] else 0 for f in flags],
        color=["#2d6a4f" if f[1] else "#9b2226" for f in flags],
    )
    ax.set_ylim(0, 1.3)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["false", "true"])
    n_src = sync.get("n_sources")
    ax.set_title(f"Constraints + sources (n_sources={n_src})")
    fig.tight_layout()
    p = out_dir / "full_api_smoke_constraints.png"
    fig.savefig(p, dpi=140)
    plt.close(fig)
    paths["constraints_png"] = str(p)

    names = (record.get("stream") or {}).get("event_names") or []
    if names:
        fig, ax = plt.subplots(figsize=(7.2, 2.4))
        order = list(range(len(names)))
        color_map = {"meta": "#1b4332", "token": "#2a6f97", "done": "#40916c", "error": "#9b2226"}
        ax.scatter(
            order,
            [0] * len(names),
            c=[color_map.get(n, "#6c757d") for n in names],
            s=[80 if n != "token" else 36 for n in names],
        )
        ax.set_yticks([])
        ax.set_xlabel("SSE event index")
        ax.set_title(
            f"Pseudo-SSE timeline (n_token={names.count('token')}, mode=pseudo)"
        )
        for i, n in enumerate(names):
            if n != "token":
                ax.annotate(n, (i, 0.02), ha="center", fontsize=8)
        fig.tight_layout()
        p = out_dir / "full_api_smoke_sse_timeline.png"
        fig.savefig(p, dpi=140)
        plt.close(fig)
        paths["sse_timeline_png"] = str(p)

    return paths


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
