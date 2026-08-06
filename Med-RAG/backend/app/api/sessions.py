"""Session CRUD + list/search — file-backed store under ``data/chat/``."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.deps import get_session_store
from app.schemas.response import success_response
from app.schemas.session import (
    SessionCreateResponse,
    SessionDeleteResponse,
    SessionDetail,
)
from app.services.session_service import epoch_to_iso, record_to_detail

router = APIRouter(tags=["sessions"])


class RenameBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


def _ok(data: Any, request: Request):
    return success_response(
        data,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/api/v1/sessions",
    response_model=None,
    summary="Create session (explicit open)",
)
def create_session(request: Request, store=Depends(get_session_store)):
    rec = store.create()
    payload = SessionCreateResponse(
        session_id=rec.session_id,
        created_at=epoch_to_iso(float(rec.created_at)),
    )
    return _ok(payload.model_dump(), request)


@router.get(
    "/api/v1/sessions",
    response_model=None,
    summary="List sessions (newest first); optional search",
)
def list_sessions(
    request: Request,
    q: str | None = Query(None, description="Filter by title/preview"),
    limit: int = Query(100, ge=1, le=500),
    store=Depends(get_session_store),
):
    items = store.list(q=q, limit=limit)
    # ISO timestamps for UI
    for row in items:
        row["created_at_iso"] = epoch_to_iso(float(row.get("created_at") or 0))
        row["updated_at_iso"] = epoch_to_iso(float(row.get("updated_at") or 0))
    return _ok({"items": items, "count": len(items)}, request)


@router.get(
    "/api/v1/sessions/{session_id}",
    response_model=None,
    summary="Get session full history",
    responses={404: {"description": "Business code **3002** — session missing/expired"}},
)
def get_session_detail(
    request: Request,
    session_id: str,
    store=Depends(get_session_store),
):
    rec = store.require(session_id)
    detail = SessionDetail.model_validate(record_to_detail(rec))
    data = detail.model_dump()
    data["title"] = getattr(rec, "title", None) or data.get("title")
    return _ok(data, request)


@router.patch(
    "/api/v1/sessions/{session_id}",
    response_model=None,
    summary="Rename session title",
)
def rename_session(
    request: Request,
    session_id: str,
    body: RenameBody,
    store=Depends(get_session_store),
):
    rec = store.rename(session_id, body.title)
    return _ok(rec.summary_dict(), request)


@router.delete(
    "/api/v1/sessions/{session_id}",
    response_model=None,
    summary="Delete session",
    responses={404: {"description": "Business code **3002** — session missing/expired"}},
)
def delete_session(
    request: Request,
    session_id: str,
    store=Depends(get_session_store),
):
    store.delete(session_id)
    payload = SessionDeleteResponse(session_id=session_id, deleted=True)
    return _ok(payload.model_dump(), request)
