"""End-to-end integration: sessions → mock /qa → stats → documents (sample)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STAGE12 = Path(__file__).resolve().parents[1]
REPO = STAGE12.parent


class _FakePipe:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, query: str, **kwargs):
        self.calls.append(query)
        return {
            "answer": f"A:{query[-40:]}",
            "sources": [{"index": 1, "chunk_id": "c1", "doc_id": "PMC176545"}],
            "constraint_checks": {"boundary_hit": False, "citation": {"ok": True}},
            "generation_metrics": {"total_time_seconds": 0.01},
            "retry_count": 0,
            "repaired": False,
        }


@pytest.fixture()
def client(tmp_path):
    for name in ("config", "bootstrap", "resources", "app"):
        sys.modules.pop(name, None)
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            sys.modules.pop(key, None)

    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(STAGE12))

    from app.bootstrap import bootstrap_paths
    from app.bridge11 import load_stage11, reset_stage11_cache
    from app.deps import get_qa_logger, get_rag_service, get_session_store, reset_singletons

    reset_stage11_cache()
    bootstrap_paths(STAGE12)
    reset_singletons()

    s11 = load_stage11()
    deps11 = s11["deps"]
    cfg = s11["config"].Stage11Config(
        session_ttl_seconds=3600,
        session_max_turns=10,
        log_dir=tmp_path,
    )
    store = deps11.MemorySessionStore(cfg)
    pipe = _FakePipe()
    rag = deps11.RagService(cfg, pipeline=pipe, inject_history=True)
    qlog = deps11.QACallLogger(cfg, query_preview_chars=40)
    qlog.path = tmp_path / "qa_calls.jsonl"

    from app.main import app

    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_rag_service] = lambda: rag
    app.dependency_overrides[get_qa_logger] = lambda: qlog
    app.dependency_overrides[deps11.get_session_store] = lambda: store
    app.dependency_overrides[deps11.get_rag_service] = lambda: rag
    app.dependency_overrides[deps11.get_qa_logger] = lambda: qlog

    yield TestClient(app), pipe, qlog

    app.dependency_overrides.clear()
    reset_singletons()
    reset_stage11_cache()


def test_chain_session_qa_stats_documents(client):
    c, pipe, qlog = client

    root = c.get("/").json()["data"]
    assert root["stage"] == "12-4"
    assert root["documents"] == "catalog"

    sid = c.post("/api/v1/sessions").json()["data"]["session_id"]

    r1 = c.post("/api/v1/qa", json={"query": "first diabetes question", "session_id": sid})
    r2 = c.post("/api/v1/qa", json={"query": "follow-up on treatment", "session_id": sid})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["data"]["session_id"] == sid
    assert len(pipe.calls) == 2

    hist = c.get(f"/api/v1/sessions/{sid}").json()["data"]
    assert hist["turn_count"] == 2
    assert "answer" in hist["turns"][0]

    # Logger should have written rows for the two QA calls
    assert qlog.path.is_file()
    lines = [ln for ln in qlog.path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) >= 2
    assert all(json.loads(ln).get("status") in {"ok", "error"} for ln in lines)

    qa_stats = c.get("/api/v1/stats/qa").json()["data"]
    assert qa_stats["total_calls"] >= 2
    assert 0.0 <= qa_stats["success_rate"] <= 1.0

    idx = c.get("/api/v1/stats/index").json()["data"]
    assert idx["document_count"] == 1000
    assert "chunk_count" in idx  # may be None if Chroma unavailable in CI
    if idx["chunk_count"] is not None:
        assert idx["document_count"] != idx["chunk_count"]
    assert idx["incremental_update_count"] == 0

    health = c.get("/api/v1/stats/health").json()["data"]
    comps = {x["name"]: x for x in health["components"]}
    assert comps["database"]["status"] == "skipped"
    assert comps["api"]["status"] == "ok"

    docs = c.get("/api/v1/documents", params={"page": 1, "page_size": 3}).json()["data"]
    assert docs["total"] == 1000 and len(docs["items"]) == 3

    # Cross-check QA source pmcid against catalog
    pmcid = r1.json()["data"]["sources"][0]["doc_id"]
    doc = c.get(f"/api/v1/documents/{pmcid}").json()
    assert doc["code"] == 0 and doc["data"]["doc_id"] == pmcid

    assert c.delete(f"/api/v1/sessions/{sid}").json()["code"] == 0


def test_openapi_tags_and_docs(client):
    c, _pipe, _qlog = client
    schema = c.get("/openapi.json").json()
    tag_names = {t["name"] for t in schema.get("tags", [])}
    for name in ("health", "qa", "sessions", "stats", "documents"):
        assert name in tag_names, f"missing OpenAPI tag: {name}"

    paths = schema["paths"]
    assert "/api/v1/sessions" in paths
    assert "/api/v1/stats/qa" in paths
    assert "/api/v1/documents" in paths
    assert "/api/v1/documents/{doc_id}" in paths

    docs = c.get("/docs")
    assert docs.status_code == 200
    redoc = c.get("/redoc")
    assert redoc.status_code == 200
