"""File-backed session store under ``Med-RAG/data/chat/``.

Drop-in replacement for the stage-11 in-memory store: same Protocol, plus ``list`` /
``search`` for the demo UI. Sessions survive process restart.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from app.config import DEFAULT_CONFIG, MedRagConfig
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

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SessionTurn":
        return cls(
            query=str(raw.get("query") or ""),
            answer=str(raw.get("answer") or ""),
            created_at=float(raw.get("created_at") or time.time()),
            meta=dict(raw.get("meta") or {}),
        )


@dataclass
class SessionRecord:
    session_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    title: str = ""
    turns: list[SessionTurn] = field(default_factory=list)

    @staticmethod
    def is_placeholder_title(title: str) -> bool:
        t = (title or "").strip().lower()
        return (not t) or t in {"new chat", "untitled", "新对话", "新聊天"}

    def display_title(self) -> str:
        if not self.is_placeholder_title(self.title):
            return self.title.strip()
        return self._auto_title()

    def to_dict(self) -> dict[str, Any]:
        # Persist raw title only — never bake placeholder "New chat" into disk,
        # or append() will think the title is already set and skip renaming.
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "title": self.title if not self.is_placeholder_title(self.title) else "",
            "turn_count": len(self.turns),
            "turns": [t.to_dict() for t in self.turns],
        }

    def _auto_title(self) -> str:
        if not self.turns:
            return "New chat"
        q = (self.turns[0].query or "").strip().replace("\n", " ")
        return (q[:48] + "…") if len(q) > 48 else (q or "New chat")

    def summary_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "title": self.display_title(),
            "turn_count": len(self.turns),
            "preview": (self.turns[-1].query[:80] if self.turns else ""),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SessionRecord":
        turns = [SessionTurn.from_dict(t) for t in (raw.get("turns") or [])]
        return cls(
            session_id=str(raw.get("session_id") or ""),
            created_at=float(raw.get("created_at") or time.time()),
            updated_at=float(raw.get("updated_at") or time.time()),
            title=str(raw.get("title") or ""),
            turns=turns,
        )


class SessionStore(Protocol):
    def create(self) -> SessionRecord: ...

    def get(self, session_id: str) -> SessionRecord | None: ...

    def require(self, session_id: str) -> SessionRecord: ...

    def append(self, session_id: str, turn: SessionTurn) -> SessionRecord: ...

    def delete(self, session_id: str) -> None: ...


class FileSessionStore:
    """JSON-per-session store under ``chat_dir`` with TTL + max_turns."""

    def __init__(self, config: MedRagConfig | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.chat_dir = Path(self.config.chat_dir)
        self.chat_dir.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._index_path = self.chat_dir / "index.json"

    def create(self) -> SessionRecord:
        with self._lock:
            sid = str(uuid.uuid4())
            rec = SessionRecord(session_id=sid)
            self._write(rec)
            self._touch_index(rec)
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
            # Rename from placeholder using the first real question
            if SessionRecord.is_placeholder_title(rec.title) and turn.query:
                q = turn.query.strip().replace("\n", " ")
                rec.title = (q[:48] + "…") if len(q) > 48 else q
            rec.updated_at = time.time()
            self._write(rec)
            self._touch_index(rec)
            return rec

    def delete(self, session_id: str) -> None:
        with self._lock:
            rec = self._get_alive_unlocked(session_id)
            if rec is None:
                raise AppException(
                    ErrorCode.SESSION_NOT_FOUND,
                    message="session not found or expired",
                    detail={"session_id": session_id},
                )
            path = self._session_path(session_id)
            if path.is_file():
                path.unlink()
            self._drop_index(session_id)

    def list(self, *, q: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Return session summaries newest-first; optional case-insensitive title/preview filter."""
        with self._lock:
            items = self._load_index()
            # Refresh from files if index empty but files exist
            if not items:
                items = self._rebuild_index_unlocked()
            out: list[dict[str, Any]] = []
            needle = (q or "").strip().lower()
            for row in items:
                sid = str(row.get("session_id") or "")
                rec = self._get_alive_unlocked(sid)
                if rec is None:
                    continue
                summary = rec.summary_dict()
                if needle:
                    blob = f"{summary.get('title','')} {summary.get('preview','')}".lower()
                    if needle not in blob:
                        continue
                out.append(summary)
                if len(out) >= max(1, limit):
                    break
            out.sort(key=lambda r: float(r.get("updated_at") or 0), reverse=True)
            return out

    def rename(self, session_id: str, title: str) -> SessionRecord:
        with self._lock:
            rec = self._get_alive_unlocked(session_id)
            if rec is None:
                raise AppException(
                    ErrorCode.SESSION_NOT_FOUND,
                    message="session not found or expired",
                    detail={"session_id": session_id},
                )
            rec.title = (title or "").strip()[:120]
            rec.updated_at = time.time()
            self._write(rec)
            self._touch_index(rec)
            return rec

    # --- internals ---

    def _session_path(self, session_id: str) -> Path:
        safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self.chat_dir / f"{safe}.json"

    def _write(self, rec: SessionRecord) -> None:
        path = self._session_path(rec.session_id)
        path.write_text(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self, session_id: str) -> SessionRecord | None:
        path = self._session_path(session_id)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return SessionRecord.from_dict(raw)
        except (OSError, ValueError, TypeError):
            return None

    def _get_alive_unlocked(self, session_id: str) -> SessionRecord | None:
        rec = self._read(session_id)
        if rec is None:
            return None
        # Heal legacy files that persisted placeholder title "New chat"
        if SessionRecord.is_placeholder_title(rec.title) and rec.turns:
            q = (rec.turns[0].query or "").strip().replace("\n", " ")
            if q:
                rec.title = (q[:48] + "…") if len(q) > 48 else q
                self._write(rec)
                self._touch_index(rec)
        ttl = max(1, int(self.config.session_ttl_seconds))
        if (time.time() - rec.updated_at) > ttl:
            path = self._session_path(session_id)
            if path.is_file():
                path.unlink()
            self._drop_index(session_id)
            return None
        return rec

    def _load_index(self) -> list[dict[str, Any]]:
        if not self._index_path.is_file():
            return []
        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
            return list(raw.get("sessions") or [])
        except (OSError, ValueError, TypeError):
            return []

    def _save_index(self, items: list[dict[str, Any]]) -> None:
        self._index_path.write_text(
            json.dumps({"sessions": items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _touch_index(self, rec: SessionRecord) -> None:
        items = [x for x in self._load_index() if x.get("session_id") != rec.session_id]
        items.insert(0, rec.summary_dict())
        self._save_index(items)

    def _drop_index(self, session_id: str) -> None:
        items = [x for x in self._load_index() if x.get("session_id") != session_id]
        self._save_index(items)

    def _rebuild_index_unlocked(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in self.chat_dir.glob("*.json"):
            if path.name == "index.json":
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                rec = SessionRecord.from_dict(raw)
                items.append(rec.summary_dict())
            except (OSError, ValueError, TypeError):
                continue
        items.sort(key=lambda r: float(r.get("updated_at") or 0), reverse=True)
        self._save_index(items)
        return items


# Back-compat name used by deps / docs
MemorySessionStore = FileSessionStore


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
