"""Health / readiness endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app import __version__
from app.config import DEFAULT_CONFIG
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.probe import probe_ollama
from app.schemas.response import ResponseModel, success_response
from app.state import RUNTIME

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    status: str = "ok"
    version: str
    retrieval_mode: str
    pipeline_backend: str
    ollama: bool | None = None
    ollama_detail: dict[str, Any] | None = None


class ReadyData(BaseModel):
    ready: bool
    pipeline_loaded: bool
    pipeline_mode: str | None = None
    pipeline_backend: str | None = None
    last_error: str | None = None


class EchoBody(BaseModel):
    """Stage-1 validation demo body (not a product API)."""

    message: str = Field(..., min_length=1, max_length=20)


@router.get("/health", response_model=ResponseModel[HealthData])
def health(
    request: Request,
    check_ollama: bool = Query(False, description="Probe Ollama /api/tags"),
) -> ResponseModel[HealthData]:
    """Process liveness. Optional Ollama probe via ``?check_ollama=true``."""
    ollama_ok: bool | None = None
    ollama_detail: dict[str, Any] | None = None
    if check_ollama:
        ollama_detail = probe_ollama()
        ollama_ok = bool(ollama_detail.get("ok"))

    data = HealthData(
        status="ok",
        version=__version__,
        retrieval_mode=DEFAULT_CONFIG.retrieval_mode,
        pipeline_backend=DEFAULT_CONFIG.pipeline_backend,
        ollama=ollama_ok,
        ollama_detail=ollama_detail,
    )
    return success_response(data.model_dump(), request_id=request.state.request_id)


@router.get("/ready", response_model=ResponseModel[ReadyData])
def ready(request: Request) -> ResponseModel[ReadyData]:
    """Pipeline readiness + index asset probe."""
    from paths import index_ready

    idx = index_ready(DEFAULT_CONFIG.retrieval_mode)
    data = ReadyData(
        ready=bool(RUNTIME.pipeline_loaded) or bool(idx.get("ready")),
        pipeline_loaded=RUNTIME.pipeline_loaded,
        pipeline_mode=RUNTIME.pipeline_mode,
        pipeline_backend=RUNTIME.pipeline_backend or DEFAULT_CONFIG.pipeline_backend,
        last_error=RUNTIME.last_error,
    )
    payload = data.model_dump()
    payload["index"] = idx
    return success_response(payload, request_id=request.state.request_id)


@router.post("/api/v1/echo", response_model=ResponseModel[dict[str, str]])
def echo(request: Request, body: EchoBody) -> ResponseModel[dict[str, str]]:
    """Tiny validated endpoint for C1 / unit tests (1001 path)."""
    return success_response(
        {"echo": body.message},
        request_id=request.state.request_id,
    )


@router.get("/api/v1/_demo_error")
def demo_error(request: Request, kind: str = Query("param")) -> None:
    """Raise ``AppException`` for handler smoke tests."""
    if kind == "param":
        raise AppException(ErrorCode.PARAM_ERROR, detail="demo param")
    if kind == "model":
        raise AppException(ErrorCode.MODEL_CALL_FAILED, detail="demo model")
    if kind == "internal":
        raise RuntimeError("demo boom")
    raise AppException(ErrorCode.PARAM_ERROR, message=f"unknown kind={kind}")
