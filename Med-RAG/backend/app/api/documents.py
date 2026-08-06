"""Document catalog API — read-only literature metadata (``doc_id`` = pmcid)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.deps import get_document_store
from app.schemas.document import DocumentIn
from app.schemas.response import PageModel, success_response
from app.services.document_store import DocumentStore

router = APIRouter(tags=["documents"])


def _success(data: Any, request: Request):
    return success_response(
        data,
        request_id=getattr(request.state, "request_id", None),
    )


def _raise_doc_not_found(doc_id: str) -> None:
    raise AppException(
        ErrorCode.DOC_NOT_FOUND,
        detail={"doc_id": doc_id},
    )


@router.get(
    "/api/v1/documents",
    response_model=None,
    summary="List documents (paginated)",
    response_description="PageModel: items / total / page / page_size",
)
def list_documents(
    request: Request,
    page: int = Query(1, ge=1, description="1-based page index"),
    page_size: int = Query(20, ge=1, le=100, description="Page size (max 100)"),
    q: str | None = Query(
        None,
        description="Optional title keyword (SQL LIKE substring)",
        examples=["Plasmodium"],
    ),
    store: DocumentStore = Depends(get_document_store),
):
    """Paginated catalog over documents sqlite; optional title filter ``q``."""
    items, total = store.list_documents(page=page, page_size=page_size, q=q)
    page_model = PageModel(
        items=[d.model_dump() for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return _success(page_model.model_dump(), request)


@router.get(
    "/api/v1/documents/{doc_id}",
    response_model=None,
    summary="Get document by pmcid",
    responses={404: {"description": "Business code **3001** — document not found"}},
)
def get_document(
    request: Request,
    doc_id: str,
    store: DocumentStore = Depends(get_document_store),
):
    """Fetch one document. ``doc_id`` is **pmcid**. Missing → **3001** (not bare 404)."""
    doc: DocumentIn | None = store.get_document(doc_id)
    if doc is None:
        _raise_doc_not_found(doc_id)
    return _success(doc.model_dump(), request)
