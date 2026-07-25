"""POST /api/v1/qa tests with mocked RagService."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STAGE11 = Path(__file__).resolve().parents[1]


class _FakePipe:
    def __init__(self) -> None:
        self.retrieval_pipeline = type("R", (), {"top_k_final": 10})()
        self.calls: list[str] = []

    def run(self, query: str, **kwargs):
        self.calls.append(query)
        return {
            "answer": f"A:{query[-20:]}",
            "sources": [{"index": 1, "chunk_id": "c1"}],
            "constraint_checks": {"boundary_hit": False, "citation": {"ok": True}},
            "generation_metrics": {"total_time_seconds": 0.01},
            "retry_count": 0,
            "repaired": False,
        }


@pytest.fixture()
def client(tmp_path):
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            sys.modules.pop(key, None)

    sys.path.insert(0, str(STAGE11))
    from app.bootstrap import bootstrap_paths
    from app.config import Stage11Config
    from app.deps import get_qa_logger, get_rag_service, get_session_store, reset_singletons
    from app.main import app
    from app.services.qa_logger import QACallLogger
    from app.services.rag_service import RagService
    from app.services.session_store import MemorySessionStore

    bootstrap_paths(STAGE11)
    reset_singletons()

    cfg = Stage11Config(session_ttl_seconds=3600, session_max_turns=10)
    store = MemorySessionStore(cfg)
    pipe = _FakePipe()
    rag = RagService(cfg, pipeline=pipe, inject_history=True)
    qlog = QACallLogger(cfg, query_preview_chars=40)
    qlog.path = tmp_path / "qa_calls.jsonl"

    app.dependency_overrides[get_rag_service] = lambda: rag
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_qa_logger] = lambda: qlog

    yield TestClient(app), store, pipe, qlog

    app.dependency_overrides.clear()
    reset_singletons()


def test_qa_success(client):
    c, store, pipe, qlog = client
    resp = c.post("/api/v1/qa", json={"query": "metformin effects", "top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["answer"].startswith("A:")
    assert data["session_id"]
    assert data["sources"]
    assert data["constraint_checks"]["citation"]["ok"] is True
    assert "X-Request-Id" in resp.headers
    assert qlog.path.is_file()
    lines = qlog.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["status"] == "ok" and row["code"] == 0


def test_qa_empty_query_1001(client):
    c, *_ = client
    resp = c.post("/api/v1/qa", json={"query": ""})
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001


def test_qa_bad_top_k_1001(client):
    c, *_ = client
    resp = c.post("/api/v1/qa", json={"query": "ok", "top_k": 999})
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001


def test_qa_session_two_turns(client):
    c, store, pipe, qlog = client
    r1 = c.post("/api/v1/qa", json={"query": "first question"})
    sid = r1.json()["data"]["session_id"]
    r2 = c.post(
        "/api/v1/qa",
        json={"query": "second question", "session_id": sid},
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["session_id"] == sid
    rec = store.require(sid)
    assert len(rec.turns) == 2
    assert rec.turns[0].query == "first question"
    assert rec.turns[1].query == "second question"
    # Second call should see history prefix in pipeline input
    assert len(pipe.calls) == 2
    assert "Conversation context" in pipe.calls[1]
    assert "second question" in pipe.calls[1]

    sess = c.get(f"/api/v1/sessions/{sid}")
    assert sess.status_code == 200
    assert sess.json()["data"]["turn_count"] == 2
