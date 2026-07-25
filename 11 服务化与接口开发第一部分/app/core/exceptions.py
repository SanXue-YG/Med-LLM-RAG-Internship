"""App exceptions and FastAPI exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_codes import ERROR_MESSAGES, ErrorCode, http_status_for
from app.core.logging import get_logger
from app.schemas.response import error_response

logger = get_logger(__name__)


class AppException(Exception):
    """Business exception carrying a stable ``ErrorCode``."""

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        detail: Any = None,
    ) -> None:
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "error")
        self.detail = detail
        super().__init__(self.message)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or "unknown"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        body = error_response(
            code=int(exc.code),
            message=exc.message,
            request_id=_request_id(request),
            data={"detail": exc.detail} if exc.detail is not None else None,
        )
        status = http_status_for(exc.code)
        logger.warning(
            "app_exception code=%s status=%s path=%s detail=%s",
            int(exc.code),
            status,
            request.url.path,
            exc.detail,
        )
        return JSONResponse(status_code=status, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Unify FastAPI's default 422 into business 1001 + HTTP 400.
        body = error_response(
            code=int(ErrorCode.PARAM_ERROR),
            message=ERROR_MESSAGES[ErrorCode.PARAM_ERROR],
            request_id=_request_id(request),
            data={"errors": exc.errors()},
        )
        logger.info(
            "validation_error path=%s errors=%s",
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(status_code=400, content=body.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = ErrorCode.INTERNAL_ERROR
        if exc.status_code == 404:
            code = ErrorCode.DOC_NOT_FOUND
        elif exc.status_code == 401:
            code = ErrorCode.AUTH_FAILED
        elif 400 <= exc.status_code < 500:
            code = ErrorCode.PARAM_ERROR
        body = error_response(
            code=int(code),
            message=str(exc.detail) if exc.detail else ERROR_MESSAGES[code],
            request_id=_request_id(request),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error path=%s", request.url.path)
        body = error_response(
            code=int(ErrorCode.INTERNAL_ERROR),
            message=ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR],
            request_id=_request_id(request),
            data={"error_type": type(exc).__name__},
        )
        return JSONResponse(status_code=500, content=body.model_dump())
