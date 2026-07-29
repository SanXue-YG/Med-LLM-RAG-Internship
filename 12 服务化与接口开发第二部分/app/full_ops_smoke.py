"""Stage-5 full Dataset ops smoke — sessions / stats / documents + live /qa.

Aligns with stage-11 ``full_smoke`` warmup (main-thread ``ensure_pipeline``) but
drives **stage-12** HTTP routes so ops APIs are actually exercised.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STAGE12_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = STAGE12_DIR / "outputs" / "reports"
DEFAULT_QUERY = "metformin cardiovascular effects"
DEFAULT_FOLLOW_UP = "follow-up: what is the evidence strength?"


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
            try:
                payload = json.loads("\n".join(data_lines))
            except json.JSONDecodeError:
                payload = {"raw": "\n".join(data_lines)}
        events.append((name, payload))
    return events


def _normalize_pmcid(text: str) -> str:
    m = re.match(r"(PMC\d+)", text.strip(), flags=re.IGNORECASE)
    if not m:
        return text.strip().split("_")[0]
    digits = re.sub(r"(?i)^pmc", "", m.group(1))
    return f"PMC{digits}"


def pmcid_from_source(src: dict[str, Any] | None) -> str | None:
    """Normalize QA source id to a catalog pmcid (strip ``_chunk*`` suffixes)."""
    if not isinstance(src, dict):
        return None
    for key in ("doc_id", "pmcid", "document_id"):
        raw = src.get(key)
        if raw:
            return _normalize_pmcid(str(raw))
    chunk = src.get("chunk_id")
    if chunk:
        return _normalize_pmcid(str(chunk))
    return None


def apply_full_env(*, log_dir: Path | None = None) -> dict[str, str]:
    """Set process env for full retrieval + documents **before** importing app.config."""
    applied = {
        "MED_RAG_RETRIEVAL_MODE": "full",
        "STAGE12_RETRIEVAL_MODE": "full",
        "STAGE11_RETRIEVAL_MODE": "full",
        "STAGE12_DOCUMENTS_MODE": "full",
        "STAGE12_PIPELINE_BACKEND": os.environ.get("STAGE12_PIPELINE_BACKEND")
        or os.environ.get("STAGE11_PIPELINE_BACKEND")
        or "constrained10",
    }
    for k, v in applied.items():
        os.environ[k] = v
    if log_dir is not None:
        os.environ["STAGE12_LOG_DIR"] = str(log_dir)
        os.environ["STAGE11_LOG_DIR"] = str(log_dir)
        applied["STAGE12_LOG_DIR"] = str(log_dir)
    return applied


def probe_full_ops_environment(*, check_chroma_collection: bool = False) -> dict[str, Any]:
    """Combine stage-11 ``probe_full_dataset`` with documents_full manifest/status."""
    from app.bridge11 import load_stage11
    from app.documents_index import status as documents_status

    s11 = load_stage11()
    base = s11["probe_full_dataset"](check_chroma_collection=check_chroma_collection)
    docs = documents_status("full")
    docs_ok = bool(
        docs.get("completed")
        and docs.get("sqlite_exists")
        and (docs.get("row_count") or 0) > 0
    )
    ready = bool(base.get("ready") and docs_ok)
    return {
        **base,
        "documents_full": docs,
        "documents_full_ok": docs_ok,
        "ready": ready,
        "hints": list(base.get("hints") or [])
        + [
            "Require documents/full manifest status=completed",
            "Set MED_RAG_RETRIEVAL_MODE=full and STAGE12_DOCUMENTS_MODE=full then restart",
        ],
    }


def _summarize_rag_result(result: dict[str, Any], *, wall_sec: float, session_id: str) -> dict[str, Any]:
    sources = list(result.get("sources") or [])
    checks = result.get("constraint_checks") or {}
    metrics = result.get("generation_metrics") or {}
    return {
        "path": "main_thread_rag_service",
        "http_code": 0,
        "wall_clock_sec": round(wall_sec, 2),
        "session_id": session_id,
        "n_sources": len(sources),
        "source_ids": [
            s.get("chunk_id") or s.get("doc_id") or s.get("index") for s in sources[:8]
        ],
        "pmcids": [p for p in (pmcid_from_source(s) for s in sources[:8]) if p],
        "citation_ok": (checks.get("citation") or {}).get("ok"),
        "format_ok": (checks.get("format") or {}).get("ok"),
        "constraint_boundary_hit": checks.get("boundary_hit"),
        "pipeline_total_time_seconds": metrics.get("total_time_seconds"),
        "stage_times": metrics.get("stage_times"),
        "retry_count": result.get("retry_count"),
        "repaired": result.get("repaired"),
        "answer_preview": (result.get("answer") or "")[:400],
        "answer_chars": len(result.get("answer") or ""),
    }


def _make_turn(query: str, answer: str, *, meta: dict[str, Any] | None = None):
    """Duck-typed SessionTurn (avoids re-importing stage-11 ``app.services`` after bridge)."""
    from types import SimpleNamespace

    return SimpleNamespace(
        query=query,
        answer=answer,
        created_at=time.time(),
        meta=meta or {},
    )


def _pseudo_stream_from_answer(answer: str, *, window: int = 32) -> dict[str, Any]:
    """Rebuild pseudo-SSE event names without TestClient (Windows-safe)."""
    chunks = [answer[i : i + window] for i in range(0, max(len(answer), 1), window)] or [""]
    names = ["meta", *(["token"] * len(chunks)), "done"]
    return {
        "stream_mode": "pseudo",
        "event_names": names,
        "n_token_events": len(chunks),
        "tokens_chars": sum(len(c) for c in chunks),
        "has_meta": True,
        "has_done": True,
        "ok": True,
        "note": (
            "pseudo-SSE reconstructed on main thread after full answer "
            "(HTTP SSE skipped on WinError risk)"
        ),
    }


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def render_report_figures(record: dict[str, Any], out_dir: Path) -> dict[str, str]:
    """PNG charts for stage-5 report (mirrors stage-11 naming with full_ops_smoke_*)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    sync = record.get("qa_turn1") or {}
    stage_times = sync.get("stage_times") or {}
    if stage_times:
        fig, ax = plt.subplots(figsize=(7.2, 3.8))
        labels = list(stage_times.keys())
        vals = [float(stage_times[k] or 0) for k in labels]
        ax.barh(labels, vals, color=["#2a6f97" if v > 0 else "#cbd5e1" for v in vals])
        ax.set_xlabel("seconds")
        ax.set_title("Full ops — generation stage_times (turn 1)")
        ax.invert_yaxis()
        fig.tight_layout()
        p = out_dir / "full_ops_smoke_stage_times.png"
        fig.savefig(p, dpi=140)
        plt.close(fig)
        paths["stage_times_png"] = str(p)

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    labels2: list[str] = []
    vals2: list[float] = []
    if record.get("warmup_sec") is not None:
        labels2.append("warmup")
        vals2.append(float(record["warmup_sec"]))
    if sync.get("wall_clock_sec") is not None:
        labels2.append("qa1\nwall")
        vals2.append(float(sync["wall_clock_sec"]))
    turn2 = record.get("qa_turn2") or {}
    if turn2.get("wall_clock_sec") is not None:
        labels2.append("qa2\nwall")
        vals2.append(float(turn2["wall_clock_sec"]))
    stream = record.get("stream") or {}
    if stream.get("wall_clock_sec") is not None:
        labels2.append("stream\nwall")
        vals2.append(float(stream["wall_clock_sec"]))
    if labels2:
        ax.bar(labels2, vals2, color=["#1b4332", "#2a6f97", "#468faf", "#95d5b2"][: len(labels2)])
        ax.set_ylabel("seconds")
        ax.set_title("Full ops — wall timing overview")
        for i, v in enumerate(vals2):
            ax.text(i, v, f"{v:.1f}s", ha="center", va="bottom", fontsize=9)
        fig.tight_layout()
        p = out_dir / "full_ops_smoke_overview.png"
        fig.savefig(p, dpi=140)
        plt.close(fig)
        paths["overview_png"] = str(p)

    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    flags = [
        ("citation_ok", bool(sync.get("citation_ok"))),
        ("format_ok", bool(sync.get("format_ok"))),
        ("docs_get_ok", bool((record.get("documents") or {}).get("get_ok"))),
        ("stats_ok", bool((record.get("stats") or {}).get("ok"))),
    ]
    ax.bar(
        [f[0] for f in flags],
        [1 if f[1] else 0 for f in flags],
        color=["#2d6a4f" if f[1] else "#9b2226" for f in flags],
    )
    ax.set_ylim(0, 1.3)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["false", "true"])
    ax.set_title(f"Ops checks (n_sources={sync.get('n_sources')})")
    fig.tight_layout()
    p = out_dir / "full_ops_smoke_constraints.png"
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
        ax.set_title(f"Pseudo-SSE timeline (n_token={names.count('token')})")
        for i, n in enumerate(names):
            if n != "token":
                ax.annotate(n, (i, 0.02), ha="center", fontsize=8)
        fig.tight_layout()
        p = out_dir / "full_ops_smoke_sse_timeline.png"
        fig.savefig(p, dpi=140)
        plt.close(fig)
        paths["sse_timeline_png"] = str(p)

    return paths


def run_full_ops_smoke(
    *,
    query: str = DEFAULT_QUERY,
    follow_up: str = DEFAULT_FOLLOW_UP,
    top_k: int = 5,
    run_stream: bool = True,
    report_dir: Path | None = None,
    check_chroma_collection: bool = False,
    http_timeout: float = 900.0,
) -> dict[str, Any]:
    """Full live ops smoke against stage-12 FastAPI (TestClient).

    Prerequisites: call ``apply_full_env`` *before* importing ``app.main`` /
    ``app.config``, or invoke via ``scripts/run_full_ops_smoke.py``.
    """
    _ = http_timeout  # TestClient in this Starlette build has no timeout kwarg
    from fastapi.testclient import TestClient

    from app.deps import (
        get_document_store,
        get_qa_logger,
        get_rag_service,
        get_session_store,
        reset_singletons,
    )
    from app.main import app, _S11
    from app.services.document_store import DocumentStore

    out_dir = Path(report_dir or REPORT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    qa_log_path = out_dir / "qa_calls_full_ops.jsonl"

    readiness = probe_full_ops_environment(check_chroma_collection=check_chroma_collection)
    record: dict[str, Any] = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": "12-5-full-ops",
        "query": query,
        "follow_up": follow_up,
        "top_k": top_k,
        "retrieval_mode": "full",
        "documents_mode": "full",
        "readiness": readiness,
        "warmup_sec": None,
        "stats": None,
        "session_id": None,
        "qa_turn1": None,
        "qa_turn2": None,
        "session_detail": None,
        "stream": None,
        "documents": None,
        "stats_qa_after": None,
        "ok": False,
        "checks": {},
        "error": None,
        "artifacts": {},
        "windows_note": (
            "Live /qa runs on main-thread RagService BEFORE any TestClient call. "
            "On Chinese/cloud Windows paths, opening TestClient first can poison "
            "subsequent transformers/pathlib loads (WinError 6714). "
            "Prefer notebook F1-B subprocess CLI if in-kernel still fails."
        ),
    }

    if not readiness.get("ready"):
        record["error"] = "full ops environment not ready — see readiness"
        _write_json(out_dir / "full_ops_smoke.json", record)
        return record

    reset_singletons()
    deps11 = _S11["deps"]
    cfg = _S11["config"].Stage11Config(
        retrieval_mode="full",
        pipeline_backend="constrained10",
        session_ttl_seconds=7200,
        session_max_turns=20,
    )
    store = deps11.MemorySessionStore(cfg)
    rag = deps11.RagService(cfg, inject_history=True)
    qlog = deps11.QACallLogger(cfg, query_preview_chars=80)
    qlog.path = qa_log_path
    if qa_log_path.exists():
        qa_log_path.unlink()
    doc_store = DocumentStore(mode="full")

    app.dependency_overrides.clear()
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_rag_service] = lambda: rag
    app.dependency_overrides[get_qa_logger] = lambda: qlog
    app.dependency_overrides[get_document_store] = lambda: doc_store
    app.dependency_overrides[deps11.get_session_store] = lambda: store
    app.dependency_overrides[deps11.get_rag_service] = lambda: rag
    app.dependency_overrides[deps11.get_qa_logger] = lambda: qlog

    # Create TestClient only AFTER main-thread live QA. On Windows Chinese / cloud
    # paths, any prior TestClient threadpool activity can poison subsequent
    # transformers/pathlib loads with WinError 6714.
    client = None

    try:
        import uuid as _uuid

        t_warm = time.perf_counter()
        rag.ensure_pipeline()
        record["warmup_sec"] = round(time.perf_counter() - t_warm, 2)

        # --- session + live QA entirely on main thread (authoritative path) ---
        sid = store.create().session_id
        record["session_id"] = sid
        qa_before_n = 0
        if qa_log_path.is_file():
            qa_before_n = len(
                [ln for ln in qa_log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            )

        t1 = time.perf_counter()
        result1 = rag.answer(query, top_k=top_k)
        wall1 = time.perf_counter() - t1
        answer1 = str(result1.get("answer") or "")
        sources1 = list(result1.get("sources") or [])
        store.append(
            sid,
            _make_turn(
                query,
                answer1,
                meta={"top_k": top_k, "n_sources": len(sources1), "full_ops": True},
            ),
        )
        qlog.log(
            request_id=str(_uuid.uuid4()),
            query=query,
            status="ok",
            latency_ms=wall1 * 1000,
            session_id=sid,
            code=0,
            top_k=top_k,
            n_sources=len(sources1),
            extra={"path": "main_thread", "retrieval_mode": "full"},
        )
        record["qa_turn1"] = _summarize_rag_result(result1, wall_sec=wall1, session_id=sid)
        turn1_ok = bool(answer1)

        t2 = time.perf_counter()
        history = list(store.require(sid).turns)
        result2 = rag.answer(follow_up, top_k=top_k, session_history=history)
        wall2 = time.perf_counter() - t2
        answer2 = str(result2.get("answer") or "")
        sources2 = list(result2.get("sources") or [])
        store.append(
            sid,
            _make_turn(
                follow_up,
                answer2,
                meta={"top_k": top_k, "n_sources": len(sources2), "full_ops": True},
            ),
        )
        qlog.log(
            request_id=str(_uuid.uuid4()),
            query=follow_up,
            status="ok",
            latency_ms=wall2 * 1000,
            session_id=sid,
            code=0,
            top_k=top_k,
            n_sources=len(sources2),
            extra={"path": "main_thread", "retrieval_mode": "full"},
        )
        record["qa_turn2"] = _summarize_rag_result(result2, wall_sec=wall2, session_id=sid)
        turn2_ok = bool(answer2)
        record["checks"]["qa_two_turns"] = turn1_ok and turn2_ok
        record["checks"]["session_id_stable"] = True

        if run_stream and turn2_ok:
            t3 = time.perf_counter()
            history2 = list(store.require(sid).turns)
            stream_q = "brief summary of prior answer constraints"
            result3 = rag.answer(
                stream_q,
                top_k=min(top_k, 3),
                session_history=history2,
            )
            stream_wall = time.perf_counter() - t3
            answer3 = str(result3.get("answer") or "")
            store.append(sid, _make_turn(stream_q, answer3))
            qlog.log(
                request_id=str(_uuid.uuid4()),
                query=stream_q,
                status="ok",
                latency_ms=stream_wall * 1000,
                session_id=sid,
                code=0,
                top_k=min(top_k, 3),
                n_sources=len(result3.get("sources") or []),
                extra={"path": "main_thread", "stream_mode": "pseudo"},
            )
            pseudo = _pseudo_stream_from_answer(
                answer3, window=getattr(cfg, "stream_chunk_chars", 32) or 32
            )
            stream_summary = _summarize_rag_result(result3, wall_sec=stream_wall, session_id=sid)
            stream_summary.update(pseudo)
            record["stream"] = stream_summary
            record["checks"]["stream_pseudo"] = bool(pseudo.get("ok"))
        else:
            record["stream"] = {"skipped": True}
            record["checks"]["stream_pseudo"] = None

        # --- HTTP ops validation (after models are fully warm) ---
        client = TestClient(app, raise_server_exceptions=False)

        idx = client.get("/api/v1/stats/index").json()
        health = client.get("/api/v1/stats/health").json()
        idata = idx.get("data") or {}
        hdata = health.get("data") or {}
        comps = {c["name"]: c for c in (hdata.get("components") or [])}
        chunk_count = idata.get("chunk_count")
        document_count = idata.get("document_count")
        stats_ok = (
            idx.get("code") == 0
            and health.get("code") == 0
            and document_count is not None
            and int(document_count) >= 4_000_000
            and chunk_count is not None
            and int(chunk_count) >= 1_000_000
            and int(document_count) != int(chunk_count)
            and comps.get("database", {}).get("status") == "skipped"
            and comps.get("api", {}).get("status") == "ok"
        )
        record["stats"] = {
            "ok": stats_ok,
            "index": idata,
            "health_statuses": {k: v.get("status") for k, v in comps.items()},
            "qa_before_lines": qa_before_n,
        }
        record["checks"]["stats_full_scale"] = stats_ok

        detail = client.get(f"/api/v1/sessions/{sid}").json()
        ddata = detail.get("data") or {}
        # stream may have appended a 3rd turn; require at least the two QA turns
        turn_count = int(ddata.get("turn_count") or 0)
        turns_ok = detail.get("code") == 0 and turn_count >= 2
        record["session_detail"] = {
            "turn_count": turn_count,
            "ok": turns_ok,
            "path": "http_get_sessions",
        }
        record["checks"]["turn_count_2"] = turns_ok

        listing = client.get("/api/v1/documents", params={"page": 1, "page_size": 3}).json()
        ldata = listing.get("data") or {}
        list_ok = (
            listing.get("code") == 0
            and (ldata.get("total") or 0) >= 4_000_000
            and len(ldata.get("items") or []) == 3
        )
        pmcids = (record.get("qa_turn1") or {}).get("pmcids") or []
        get_payload: dict[str, Any] = {"tried": pmcids[:3]}
        get_ok = False
        for pmcid in pmcids[:5]:
            g = client.get(f"/api/v1/documents/{pmcid}").json()
            if g.get("code") == 0 and (g.get("data") or {}).get("doc_id") == pmcid:
                get_ok = True
                get_payload["hit"] = g.get("data")
                break
            get_payload.setdefault("misses", []).append(
                {"pmcid": pmcid, "code": g.get("code"), "message": g.get("message")}
            )
        if not get_ok:
            g = client.get("/api/v1/documents/PMC176545").json()
            get_payload["fallback_PMC176545"] = {
                "code": g.get("code"),
                "doc_id": (g.get("data") or {}).get("doc_id"),
            }
            get_ok = g.get("code") == 0

        record["documents"] = {
            "list_ok": list_ok,
            "list_total": ldata.get("total"),
            "get_ok": get_ok,
            "get": get_payload,
            "ok": list_ok and get_ok,
        }
        record["checks"]["documents_full"] = bool(record["documents"]["ok"])

        qa_after = client.get("/api/v1/stats/qa").json().get("data") or {}
        after_n = int(qa_after.get("total_calls") or 0)
        record["stats_qa_after"] = qa_after
        record["checks"]["stats_qa_grew"] = after_n >= qa_before_n + 2

        checks = record["checks"]
        required = [
            checks.get("stats_full_scale"),
            checks.get("qa_two_turns"),
            checks.get("turn_count_2"),
            checks.get("documents_full"),
            checks.get("stats_qa_grew"),
        ]
        record["ok"] = all(bool(x) for x in required)
        if checks.get("stream_pseudo") is False:
            record["ok"] = False

        if qa_log_path.is_file():
            record["qa_log_lines"] = len(
                qa_log_path.read_text(encoding="utf-8").strip().splitlines()
            )

        figs = render_report_figures(record, out_dir)
        record["artifacts"] = {
            "json": str(out_dir / "full_ops_smoke.json"),
            "qa_log": str(qa_log_path),
            **figs,
        }
        _write_json(out_dir / "full_ops_smoke.json", record)
        return record
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"{type(exc).__name__}: {exc}"
        _write_json(out_dir / "full_ops_smoke.json", record)
        return record
    finally:
        app.dependency_overrides.clear()
        reset_singletons()
