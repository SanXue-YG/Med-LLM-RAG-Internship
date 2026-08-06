"""Ingest / corpus-update API for the Med-RAG demo."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Request, UploadFile

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.schemas.response import success_response
from paths import index_ready

router = APIRouter(tags=["ingest"])


@router.get("/api/v1/ingest/status", response_model=None, summary="Index readiness")
def ingest_status(request: Request):
    idx = index_ready("sample")
    return success_response(
        idx,
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/api/v1/ingest/upload",
    response_model=None,
    summary="Upload XML/JSONL and index into sample corpus",
)
async def ingest_upload(request: Request, file: UploadFile = File(...)):
    """Accept ``.xml`` / ``.jsonl`` / ``.json``, parse → chunk → Chroma add + documents upsert.

    Writes only under ``Med-RAG/data/``. Resets pipeline singleton after success.
    """
    if not file.filename:
        raise AppException(ErrorCode.PARAM_ERROR, detail="filename required")
    content = await file.read()
    if not content:
        raise AppException(ErrorCode.PARAM_ERROR, detail="empty file")
    if len(content) > 32 * 1024 * 1024:
        raise AppException(ErrorCode.PARAM_ERROR, detail="file too large (max 32MB for demo)")

    try:
        from ingest import run_ingest_file, save_upload

        path = save_upload(file.filename, content)
        result: dict[str, Any] = run_ingest_file(path)
    except ValueError as exc:
        raise AppException(ErrorCode.PARAM_ERROR, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise AppException(
            ErrorCode.PIPELINE_FAILED,
            message="ingest failed",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not result.get("ok"):
        raise AppException(
            ErrorCode.PIPELINE_FAILED,
            message="ingest produced no documents",
            detail=result,
        )
    return success_response(result, request_id=getattr(request.state, "request_id", None))
