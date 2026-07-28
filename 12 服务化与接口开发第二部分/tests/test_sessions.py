"""Stage-1 session CRUD tests (shared store with mocked /qa)."""

from __future__ import annotations

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
    cfg = s11["config"].Stage11Config(session_ttl_seconds=3600, session_max_turns=10)
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

    yield TestClient(app), store, pipe

    app.dependency_overrides.clear()
    reset_singletons()
    reset_stage11_cache()


def test_create_get_delete(client):
    c, store, _pipe = client
    r = c.post("/api/v1/sessions")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    sid = body["data"]["session_id"]
    assert body["data"]["created_at"].endswith("Z")

    g = c.get(f"/api/v1/sessions/{sid}")
    assert g.status_code == 200
    data = g.json()["data"]
    assert data["session_id"] == sid
    assert data["turn_count"] == 0
    assert data["turns"] == []

    d = c.delete(f"/api/v1/sessions/{sid}")
    assert d.status_code == 200
    assert d.json()["data"]["deleted"] is True

    missing = c.get(f"/api/v1/sessions/{sid}")
    assert missing.status_code == 404
    assert missing.json()["code"] == 3002

    again = c.delete(f"/api/v1/sessions/{sid}")
    assert again.status_code == 404
    assert again.json()["code"] == 3002


def test_qa_two_turns_then_full_history(client):
    c, store, pipe = client
    created = c.post("/api/v1/sessions").json()["data"]["session_id"]

    r1 = c.post(
        "/api/v1/qa",
        json={"query": "first question about diabetes", "session_id": created},
    )
    assert r1.status_code == 200
    assert r1.json()["data"]["session_id"] == created

    r2 = c.post(
        "/api/v1/qa",
        json={"query": "second follow-up question", "session_id": created},
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["session_id"] == created

    detail = c.get(f"/api/v1/sessions/{created}").json()["data"]
    assert detail["turn_count"] == 2
    assert len(detail["turns"]) == 2
    assert detail["turns"][0]["query"] == "first question about diabetes"
    assert "answer" in detail["turns"][0]
    assert "answer_preview" not in detail["turns"][0]
    assert detail["turns"][1]["query"] == "second follow-up question"
    assert len(pipe.calls) == 2
    assert "Conversation context" in pipe.calls[1]


def test_qa_bad_id_autocreate_vs_get_3002(client):
    c, _store, _pipe = client
    qa = c.post("/api/v1/qa", json={"query": "orphan query", "session_id": "not-a-real-id"})
    assert qa.status_code == 200
    new_sid = qa.json()["data"]["session_id"]
    assert new_sid != "not-a-real-id"

    bad = c.get("/api/v1/sessions/not-a-real-id")
    assert bad.status_code == 404
    assert bad.json()["code"] == 3002

    ok = c.get(f"/api/v1/sessions/{new_sid}")
    assert ok.status_code == 200
    assert ok.json()["data"]["turn_count"] == 1
