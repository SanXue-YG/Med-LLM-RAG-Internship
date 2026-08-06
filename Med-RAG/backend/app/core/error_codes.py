"""Business error codes for the Medical RAG API."""

from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    OK = 0
    PARAM_ERROR = 1001
    AUTH_FAILED = 2001
    DOC_NOT_FOUND = 3001
    SESSION_NOT_FOUND = 3002
    MODEL_CALL_FAILED = 4001
    PIPELINE_FAILED = 4002
    INTERNAL_ERROR = 5000


# Default human-readable messages (handlers may override).
ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.OK: "ok",
    ErrorCode.PARAM_ERROR: "parameter error",
    ErrorCode.AUTH_FAILED: "authentication failed",
    ErrorCode.DOC_NOT_FOUND: "document not found",
    ErrorCode.SESSION_NOT_FOUND: "session not found",
    ErrorCode.MODEL_CALL_FAILED: "model call failed",
    ErrorCode.PIPELINE_FAILED: "pipeline failed",
    ErrorCode.INTERNAL_ERROR: "internal error",
}


def http_status_for(code: ErrorCode) -> int:
    """Map business code → HTTP status."""
    if code == ErrorCode.OK:
        return 200
    if code == ErrorCode.PARAM_ERROR:
        return 400
    if code == ErrorCode.AUTH_FAILED:
        return 401
    if code in (ErrorCode.DOC_NOT_FOUND, ErrorCode.SESSION_NOT_FOUND):
        return 404
    if code in (ErrorCode.MODEL_CALL_FAILED, ErrorCode.PIPELINE_FAILED):
        return 502
    return 500
