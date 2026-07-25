"""POST /api/v1/qa/stream pseudo-SSE tests with mocked RagService."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STAGE11 = Path(__file__).resolve().parents[1]


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    """Parse ``event:`` / ``data:`` blocks into ``(event, data_dict)`` list."""
    events: list[tuple[str, dict]] = []
    blocks = [b for b in raw.split("\n\n") if b.strip()]
    for block in blocks:
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        payload = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append((event_name, payload))
    return events


class _FakePipe:
    def __init__(self, answer: str = "Sentence one. Sentence two!") -> None:
        self.retrieval_pipeline = type("R", (), {"top_k_final": 10})()
        self.answer = answer
        self.fail: Exception | None = None

    def run(self, query: str, **kwargs):
        if self.fail is not None:
            raise self.fail
        return {
            "answer": self.answer,
            "sources": [{"index": 1, "chunk_id": "c1"}],
            "constraint_checks": {"boundary_hit": False, "citation": {"ok": True}},
            "generation_metrics": {"total_time_seconds": 0.01},
            "retry_count": 0,
            "repaired": False,
        }


@pytest.fixture()
def stream_client(tmp_path):
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

    cfg = Stage11Config(session_ttl_seconds=3600, stream_chunk_chars=12)
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


def test_stream_meta_token_done(stream_client):
    c, store, pipe, qlog = stream_client
    with c.stream(
        "POST",
        "/api/v1/qa/stream",
        json={"query": "metformin effects", "top_k": 5},
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        assert resp.headers.get("X-Stream-Mode") == "pseudo"
        raw = "".join(resp.iter_text())

    events = parse_sse(raw)
    names = [n for n, _ in events]
    assert names[0] == "meta"
    assert "done" in names
    assert "error" not in names
    assert names.count("token") >= 1

    meta = events[0][1]
    assert meta["stream_mode"] == "pseudo"
    assert meta["request_id"]
    sid = meta["session_id"]
    assert sid

    tokens = "".join(d["text"] for n, d in events if n == "token")
    done = next(d for n, d in events if n == "done")
    assert tokens == done["answer"] == pipe.answer
    assert done["sources"]
    assert done["constraint_checks"]["citation"]["ok"] is True
    assert done["stream_mode"] == "pseudo"
    assert done["session_id"] == sid
    assert len(store.require(sid).turns) == 1

    lines = qlog.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["status"] == "ok" and row["stream_mode"] == "pseudo"


def test_stream_validation_still_json_1001(stream_client):
    c, *_ = stream_client
    resp = c.post("/api/v1/qa/stream", json={"query": ""})
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001


def test_stream_error_event(stream_client):
    from app.core.error_codes import ErrorCode
    from app.core.exceptions import AppException

    c, _, pipe, qlog = stream_client
    pipe.fail = AppException(ErrorCode.MODEL_CALL_FAILED, detail="down")

    with c.stream(
        "POST",
        "/api/v1/qa/stream",
        json={"query": "anything"},
    ) as resp:
        assert resp.status_code == 200
        raw = "".join(resp.iter_text())

    events = parse_sse(raw)
    names = [n for n, _ in events]
    assert names[0] == "meta"
    assert "error" in names
    assert "done" not in names
    err = next(d for n, d in events if n == "error")
    assert err["code"] == int(ErrorCode.MODEL_CALL_FAILED)
    assert err["request_id"]
    assert err["stream_mode"] == "pseudo"

    row = json.loads(qlog.path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["status"] == "error"
