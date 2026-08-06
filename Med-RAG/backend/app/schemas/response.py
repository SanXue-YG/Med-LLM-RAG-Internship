"""Unified JSON response envelopes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class ResponseModel(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None
    request_id: str
    timestamp: str = Field(default_factory=utc_now_iso)


class PageModel(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


def success_response(
    data: Any,
    *,
    request_id: str,
    message: str = "ok",
) -> ResponseModel[Any]:
    return ResponseModel(
        code=0,
        message=message,
        data=data,
        request_id=request_id,
        timestamp=utc_now_iso(),
    )


def error_response(
    *,
    code: int,
    message: str,
    request_id: str,
    data: Any = None,
) -> ResponseModel[Any]:
    return ResponseModel(
        code=code,
        message=message,
        data=data,
        request_id=request_id,
        timestamp=utc_now_iso(),
    )
