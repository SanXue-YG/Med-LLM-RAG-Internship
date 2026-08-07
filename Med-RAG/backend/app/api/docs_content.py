"""Serve package docs markdown for the demo UI viewer."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request

from app.config import MED_RAG_HOME
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.schemas.response import success_response

router = APIRouter(tags=["docs"])

# Whitelist only known package docs (no arbitrary path read)
_DOC_FILES: dict[str, str] = {
    "code": "代码说明文档.md",
    "flow": "流程图.md",
    "deploy": "部署文档.md",
    "data": "数据存储与导入参考.md",
}


@router.get("/api/v1/docs/{slug}", response_model=None, summary="Read a package markdown doc")
def get_doc(slug: str, request: Request):
    name = _DOC_FILES.get(slug)
    if not name:
        raise AppException(
            ErrorCode.PARAM_ERROR,
            message="unknown doc slug",
            detail={"slug": slug, "allowed": list(_DOC_FILES)},
        )
    path = MED_RAG_HOME / "docs" / name
    if not path.is_file():
        raise AppException(
            ErrorCode.DOC_NOT_FOUND,
            message="doc file missing",
            detail={"path": str(path)},
        )
    text = path.read_text(encoding="utf-8")
    return success_response(
        {
            "slug": slug,
            "filename": name,
            "title": Path(name).stem,
            "markdown": text,
        },
        request_id=getattr(request.state, "request_id", None) or "docs",
    )


@router.get("/api/v1/docs", response_model=None, summary="List available package docs")
def list_docs(request: Request):
    items = [
        {"slug": slug, "filename": name, "title": Path(name).stem}
        for slug, name in _DOC_FILES.items()
    ]
    return success_response(
        {"items": items},
        request_id=getattr(request.state, "request_id", None) or "docs",
    )
