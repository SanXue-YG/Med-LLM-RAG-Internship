"""Stage-12 ops stats unit tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STAGE12 = Path(__file__).resolve().parents[1]
REPO = STAGE12.parent


@pytest.fixture()
def boot(tmp_path):
    for name in ("config", "bootstrap", "resources", "app"):
        sys.modules.pop(name, None)
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            sys.modules.pop(key, None)

    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(STAGE12))

    from app.bootstrap import bootstrap_paths
    from app.bridge11 import reset_stage11_cache

    reset_stage11_cache()
    bootstrap_paths(STAGE12)
    return tmp_path


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def test_aggregate_qa_stats_fixture(boot):
    from app.services.stats_service import aggregate_qa_stats

    path = _write_jsonl(
        boot / "qa_calls.jsonl",
        [
            {"status": "ok", "latency_ms": 1000.0, "code": 0},
            {"status": "ok", "latency_ms": 2000.0, "code": 0},
            {"status": "error", "latency_ms": 500.0, "code": 1001},
            {"status": "ok", "latency_ms": "bad"},  # counted; latency skipped
        ],
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write("not-json\n")
        fh.write("\n")

    stats = aggregate_qa_stats(path)
    assert stats.total_calls == 4
    assert stats.success_count == 3
    assert stats.failure_count == 1
    assert stats.success_rate == pytest.approx(0.75)
    assert stats.avg_latency_seconds == pytest.approx((1000 + 2000 + 500) / 3 / 1000.0)


def test_aggregate_qa_stats_empty_and_missing(boot):
    from app.services.stats_service import aggregate_qa_stats

    empty = boot / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    z = aggregate_qa_stats(empty)
    assert z.total_calls == 0
    assert z.success_rate == 0.0
    assert z.avg_latency_seconds == 0.0

    missing = aggregate_qa_stats(boot / "nope.jsonl")
    assert missing.total_calls == 0


def test_stats_endpoints(boot, monkeypatch):
    from app.bridge11 import load_stage11, reset_stage11_cache
    from app.deps import get_qa_logger, reset_singletons

    reset_singletons()
    s11 = load_stage11()
    deps11 = s11["deps"]
    cfg = s11["config"].Stage11Config(
        session_ttl_seconds=3600,
        session_max_turns=10,
        log_dir=boot,
    )
    qlog = deps11.QACallLogger(cfg, query_preview_chars=40)
    qlog.path = boot / "qa_calls.jsonl"
    _write_jsonl(
        qlog.path,
        [
            {"status": "ok", "latency_ms": 1500.0, "code": 0},
            {"status": "error", "latency_ms": 500.0, "code": 2001},
        ],
    )

    # Avoid real Ollama / heavy chroma in health unit path for llm detail shape
    monkeypatch.setitem(
        s11,
        "probe_ollama",
        lambda *a, **k: {
            "ok": True,
            "base_url": "http://127.0.0.1:11434",
            "model_configured": "deepseek-r1:7b",
            "model_present": True,
            "models_sample": ["deepseek-r1:7b"],
        },
    )

    from app.main import app

    app.dependency_overrides[get_qa_logger] = lambda: qlog
    client = TestClient(app)

    qa = client.get("/api/v1/stats/qa")
    assert qa.status_code == 200
    body = qa.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["total_calls"] == 2
    assert data["success_count"] == 1
    assert data["failure_count"] == 1
    assert data["success_rate"] == pytest.approx(0.5)
    assert data["avg_latency_seconds"] == pytest.approx(1.0)

    idx = client.get("/api/v1/stats/index")
    assert idx.status_code == 200
    idata = idx.json()["data"]
    assert "chunk_count" in idata and "document_count" in idata
    assert idata["incremental_update_count"] == 0
    # sample: docs≈1000, chunks≈1267 — must not be confused
    if idata.get("document_count") is not None and idata.get("chunk_count") is not None:
        assert idata["document_count"] != idata["chunk_count"]

    health = client.get("/api/v1/stats/health")
    assert health.status_code == 200
    comps = {c["name"]: c for c in health.json()["data"]["components"]}
    assert comps["database"]["status"] == "skipped"
    assert comps["api"]["status"] == "ok"
    assert comps["llm"]["status"] == "ok"
    assert comps["vector_db"]["status"] in {"ok", "degraded", "down"}

    root = client.get("/")
    assert root.json()["data"]["stage"] == "12-4"
    assert root.json()["data"]["stats"] == "qa+index+health"
    assert root.json()["data"]["documents"] == "catalog"

    app.dependency_overrides.clear()
    reset_singletons()
    reset_stage11_cache()
