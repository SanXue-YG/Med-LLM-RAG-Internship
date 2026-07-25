"""QA request / response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.config import DEFAULT_CONFIG


class QARequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=DEFAULT_CONFIG.query_max_length,
        description="User question (non-empty)",
    )
    top_k: int = Field(
        DEFAULT_CONFIG.top_k_default,
        ge=DEFAULT_CONFIG.top_k_min,
        le=DEFAULT_CONFIG.top_k_max,
        description="Final retrieval / sources budget",
    )
    session_id: str | None = Field(
        None,
        description="Optional session id; omit to create a new session",
    )


class QAResponseData(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str
    generation_metrics: dict[str, Any] | None = None
    constraint_checks: dict[str, Any] | None = None
    retry_count: int | None = None
    repaired: bool | None = None
    top_k_applied: int | None = None
    top_k_mode: str | None = None
