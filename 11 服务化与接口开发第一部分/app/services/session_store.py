"""In-process session store (MVP). Persistence can follow later."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Protocol

from app.config import DEFAULT_CONFIG, Stage11Config
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException


@dataclass
class SessionTurn:
    query: str
    answer: str
    created_at: float = field(default_factory=time.time)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "created_at": self.created_at,
            "meta": self.meta,
        }


@dataclass
class SessionRecord:
    session_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turns: list[SessionTurn] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turn_count": len(self.turns),
            "turns": [t.to_dict() for t in self.turns],
        }


class SessionStore(Protocol):
    def create(self) -> SessionRecord: ...

    def get(self, session_id: str) -> SessionRecord | None: ...

    def require(self, session_id: str) -> SessionRecord: ...

    def append(self, session_id: str, turn: SessionTurn) -> SessionRecord: ...

    def delete(self, session_id: str) -> None: ...


class MemorySessionStore:
    """Process-local dict store with TTL + max_turns.

    Expiry policy
    -------------
    - ``get`` / missing id / expired → ``None``（条目会被删除）
    - ``require`` → 同上情况抛 ``AppException(SESSION_NOT_FOUND=3002)``
    - 阶段 3 的 HTTP 层可选择：``require`` 报 3002，或 ``get`` 为 None 时 ``create`` 自动新建
    """

    def __init__(self, config: Stage11Config | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = RLock()

    def create(self) -> SessionRecord:
        with self._lock:
            sid = str(uuid.uuid4())
            rec = SessionRecord(session_id=sid)
            self._sessions[sid] = rec
            return rec

    def get(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._get_alive_unlocked(session_id)

    def require(self, session_id: str) -> SessionRecord:
        rec = self.get(session_id)
        if rec is None:
            raise AppException(
                ErrorCode.SESSION_NOT_FOUND,
                message="session not found or expired",
                detail={"session_id": session_id},
            )
        return rec

    def append(self, session_id: str, turn: SessionTurn) -> SessionRecord:
        with self._lock:
            rec = self._get_alive_unlocked(session_id)
            if rec is None:
                raise AppException(
                    ErrorCode.SESSION_NOT_FOUND,
                    message="session not found or expired",
                    detail={"session_id": session_id},
                )
            rec.turns.append(turn)
            max_turns = max(1, int(self.config.session_max_turns))
            if len(rec.turns) > max_turns:
                rec.turns = rec.turns[-max_turns:]
            rec.updated_at = time.time()
            return rec

    def delete(self, session_id: str) -> None:
        """Remove a live session. Missing/expired → ``SESSION_NOT_FOUND`` (3002)."""
        with self._lock:
            rec = self._get_alive_unlocked(session_id)
            if rec is None:
                raise AppException(
                    ErrorCode.SESSION_NOT_FOUND,
                    message="session not found or expired",
                    detail={"session_id": session_id},
                )
            self._sessions.pop(session_id, None)

    def _get_alive_unlocked(self, session_id: str) -> SessionRecord | None:
        rec = self._sessions.get(session_id)
        if rec is None:
            return None
        ttl = max(1, int(self.config.session_ttl_seconds))
        if (time.time() - rec.updated_at) > ttl:
            self._sessions.pop(session_id, None)
            return None
        return rec


def format_session_prefix(
    turns: list[SessionTurn],
    *,
    max_turns: int = 3,
    answer_clip: int = 200,
    max_chars: int = 800,
) -> str:
    """Build a short history prefix to prepend onto the current query (MVP)."""
    if not turns:
        return ""
    recent = turns[-max(1, max_turns) :]
    parts: list[str] = ["[Conversation context]"]
    for i, turn in enumerate(recent, start=1):
        ans = (turn.answer or "").strip().replace("\n", " ")
        if len(ans) > answer_clip:
            ans = ans[:answer_clip] + "…"
        q = (turn.query or "").strip().replace("\n", " ")
        parts.append(f"Previous Q{i}: {q}")
        parts.append(f"Previous A{i}: {ans}")
    parts.append("")
    parts.append("[Current question]")
    text = "\n".join(parts) + "\n"
    if len(text) > max_chars:
        text = text[-max_chars:]
    return text
