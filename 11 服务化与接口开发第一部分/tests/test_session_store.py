"""SessionStore unit tests."""

from __future__ import annotations

import time

import pytest

from app.config import Stage11Config
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.services.session_store import (
    MemorySessionStore,
    SessionTurn,
    format_session_prefix,
)


def test_create_get_append():
    store = MemorySessionStore(Stage11Config(session_ttl_seconds=3600, session_max_turns=10))
    rec = store.create()
    assert store.get(rec.session_id) is not None
    store.append(rec.session_id, SessionTurn(query="q1", answer="a1"))
    store.append(rec.session_id, SessionTurn(query="q2", answer="a2"))
    got = store.require(rec.session_id)
    assert len(got.turns) == 2
    assert got.turns[0].query == "q1"


def test_max_turns_trims():
    store = MemorySessionStore(Stage11Config(session_ttl_seconds=3600, session_max_turns=2))
    rec = store.create()
    for i in range(5):
        store.append(rec.session_id, SessionTurn(query=f"q{i}", answer=f"a{i}"))
    got = store.require(rec.session_id)
    assert len(got.turns) == 2
    assert got.turns[0].query == "q3"
    assert got.turns[1].query == "q4"


def test_ttl_expires(monkeypatch):
    store = MemorySessionStore(Stage11Config(session_ttl_seconds=1, session_max_turns=10))
    rec = store.create()
    # Force updated_at into the past
    store._sessions[rec.session_id].updated_at = time.time() - 10
    assert store.get(rec.session_id) is None
    with pytest.raises(AppException) as ei:
        store.require(rec.session_id)
    assert ei.value.code == ErrorCode.SESSION_NOT_FOUND


def test_append_missing_raises_3002():
    store = MemorySessionStore()
    with pytest.raises(AppException) as ei:
        store.append("no-such", SessionTurn(query="q", answer="a"))
    assert ei.value.code == ErrorCode.SESSION_NOT_FOUND


def test_delete_and_missing_3002():
    store = MemorySessionStore(Stage11Config(session_ttl_seconds=3600, session_max_turns=10))
    rec = store.create()
    store.delete(rec.session_id)
    assert store.get(rec.session_id) is None
    with pytest.raises(AppException) as ei:
        store.delete(rec.session_id)
    assert ei.value.code == ErrorCode.SESSION_NOT_FOUND


def test_format_session_prefix():
    turns = [
        SessionTurn(query="What is MI?", answer="Myocardial infarction ..."),
        SessionTurn(query="Treatment?", answer="Reperfusion and antiplatelet therapy."),
    ]
    text = format_session_prefix(turns, max_turns=2)
    assert "Conversation context" in text
    assert "Current question" in text
    assert "What is MI?" in text
