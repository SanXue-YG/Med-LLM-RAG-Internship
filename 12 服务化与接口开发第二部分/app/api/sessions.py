"""Session CRUD — shared MemorySessionStore with ``POST /api/v1/qa``.

Policy
------
- ``POST /sessions``：显式开桌
- ``GET /sessions/{id}`` / ``DELETE``：无效或过期 → **3002**（``store.require`` / ``delete``）
- ``POST /qa``：无效 id **自动新建**（阶段 11 行为，与上列故意不一致）
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.deps import get_session_store
from app.schemas.session import (
    SessionCreateResponse,
    SessionDeleteResponse,
    SessionDetail,
)
from app.services.session_service import epoch_to_iso, record_to_detail

router = APIRouter(tags=["sessions"])


def _success(data: Any, request: Request):
    from app.bridge11 import load_stage11

    return load_stage11()["success_response"](
        data,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/api/v1/sessions",
    response_model=None,
    summary="Create session (explicit open)",
    response_description="Envelope with session_id + created_at (UTC Z)",
)
def create_session(request: Request, store=Depends(get_session_store)):
    """Open an empty conversation desk.

    Returns ``session_id`` for subsequent ``POST /qa`` and history lookup.
    """
    rec = store.create()
    payload = SessionCreateResponse(
        session_id=rec.session_id,
        created_at=epoch_to_iso(float(rec.created_at)),
    )
    return _success(payload.model_dump(), request)


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
    """Return complete ``turns`` (full ``answer``, not preview). Missing/expired → 3002."""
    rec = store.require(session_id)
    detail = SessionDetail.model_validate(record_to_detail(rec))
    return _success(detail.model_dump(), request)


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
    """Remove session. Missing/expired → 3002 (same as GET; not idempotent 200)."""
    store.delete(session_id)
    payload = SessionDeleteResponse(session_id=session_id, deleted=True)
    return _success(payload.model_dump(), request)
