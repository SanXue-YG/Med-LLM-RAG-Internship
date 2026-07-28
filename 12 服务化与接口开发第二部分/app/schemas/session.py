"""Session API response models (stage 12)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    session_id: str
    created_at: str


class SessionTurnOut(BaseModel):
    """One QA turn = one SessionTurn (not separate user/assistant messages)."""

    query: str
    answer: str
    created_at: str
    meta: dict[str, Any] | None = None


class SessionDetail(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    turn_count: int
    turns: list[SessionTurnOut] = Field(default_factory=list)


class SessionDeleteResponse(BaseModel):
    session_id: str
    deleted: bool = True
