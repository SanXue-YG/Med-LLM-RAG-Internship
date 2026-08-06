"""QA HTTP API — sync JSON and pseudo-SSE streaming."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.error_codes import ERROR_MESSAGES, ErrorCode
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.deps import get_qa_logger, get_rag_service, get_session_store
from app.schemas.qa import QARequest, QAResponseData
from app.schemas.response import ResponseModel, success_response, utc_now_iso
from app.services.qa_logger import QACallLogger
from app.services.rag_service import RagService
from app.services.session_store import MemorySessionStore, SessionTurn
from app.services.sse_pseudo import format_sse, iter_pseudo_tokens

logger = get_logger("api.qa")
router = APIRouter(tags=["qa"])

STREAM_MODE = "pseudo"  # MVP; future: "token" if upstream supports it


def _resolve_session(
    store: MemorySessionStore,
    session_id: str | None,
) -> tuple[str, list[SessionTurn], bool]:
    """Return ``(session_id, history_turns, created_new)``.

    Policy: missing/expired ``session_id`` → **auto-create** a new session
    (friendlier for API clients than hard 3002). Use ``store.require`` elsewhere
    if strict 3002 is needed.
    """
    if not session_id:
        rec = store.create()
        return rec.session_id, [], True

    rec = store.get(session_id)
    if rec is None:
        rec = store.create()
        logger.info("session_missing_or_expired old=%s new=%s", session_id, rec.session_id)
        return rec.session_id, [], True

    return rec.session_id, list(rec.turns), False


@router.post("/api/v1/qa", response_model=ResponseModel[QAResponseData])
def qa(
    request: Request,
    body: QARequest,
    rag: RagService = Depends(get_rag_service),
    store: MemorySessionStore = Depends(get_session_store),
    qa_logger: QACallLogger = Depends(get_qa_logger),
) -> ResponseModel[QAResponseData]:
    """Synchronous medical QA (blocks until pipeline finishes)."""
    request_id = request.state.request_id
    started = time.perf_counter()
    sid, history, created_new = _resolve_session(store, body.session_id)

    try:
        result = rag.answer(
            body.query,
            top_k=body.top_k,
            session_history=history or None,
        )
        answer = str(result.get("answer") or "")
        sources = list(result.get("sources") or [])
        store.append(
            sid,
            SessionTurn(
                query=body.query,
                answer=answer,
                meta={
                    "top_k": body.top_k,
                    "n_sources": len(sources),
                    "sources": sources,
                },
            ),
        )
        data = QAResponseData(
            answer=answer,
            sources=sources,
            session_id=sid,
            generation_metrics=result.get("generation_metrics"),
            constraint_checks=result.get("constraint_checks"),
            retry_count=result.get("retry_count"),
            repaired=result.get("repaired"),
            top_k_applied=result.get("top_k_applied"),
            top_k_mode=result.get("top_k_mode"),
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        qa_logger.log(
            request_id=request_id,
            query=body.query,
            status="ok",
            latency_ms=elapsed_ms,
            session_id=sid,
            code=0,
            top_k=body.top_k,
            n_sources=len(sources),
            extra={"session_created": created_new},
        )
        return success_response(data.model_dump(), request_id=request_id)
    except AppException as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        qa_logger.log(
            request_id=request_id,
            query=body.query,
            status="error",
            latency_ms=elapsed_ms,
            session_id=sid,
            code=int(exc.code),
            top_k=body.top_k,
            error_detail=exc.detail,
            extra={"session_created": created_new},
        )
        raise
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = (time.perf_counter() - started) * 1000
        qa_logger.log(
            request_id=request_id,
            query=body.query,
            status="error",
            latency_ms=elapsed_ms,
            session_id=sid,
            code=int(ErrorCode.INTERNAL_ERROR),
            top_k=body.top_k,
            error_detail=f"{type(exc).__name__}: {exc}",
            extra={"session_created": created_new},
        )
        raise AppException(
            ErrorCode.INTERNAL_ERROR,
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc


@router.post(
    "/api/v1/qa/stream",
    summary="Pseudo-streaming QA (SSE)",
    description=(
        "Server-Sent Events: ``meta`` → ``token``* → ``done`` (or ``error``). "
        "**MVP = pseudo-stream**: runs the same full ``rag_service.answer`` as "
        "``POST /api/v1/qa``, then chunks the finished answer. "
        "Not Ollama token-level streaming (``stream_mode=pseudo``)."
    ),
    response_class=StreamingResponse,
)
def qa_stream(
    request: Request,
    body: QARequest,
    rag: RagService = Depends(get_rag_service),
    store: MemorySessionStore = Depends(get_session_store),
    qa_logger: QACallLogger = Depends(get_qa_logger),
) -> StreamingResponse:
    """Pseudo-SSE QA; validation errors still return JSON 400 + code=1001."""
    request_id = request.state.request_id

    def event_gen() -> Iterator[str]:
        started = time.perf_counter()
        sid, history, created_new = _resolve_session(store, body.session_id)
        yield format_sse(
            "meta",
            {
                "request_id": request_id,
                "session_id": sid,
                "stream_mode": STREAM_MODE,
                "session_created": created_new,
            },
        )

        try:
            result = rag.answer(
                body.query,
                top_k=body.top_k,
                session_history=history or None,
            )
            answer = str(result.get("answer") or "")
            sources = list(result.get("sources") or [])
            store.append(
                sid,
                SessionTurn(
                    query=body.query,
                    answer=answer,
                    meta={
                        "top_k": body.top_k,
                        "n_sources": len(sources),
                        "sources": sources,
                        "stream": True,
                    },
                ),
            )
            window = getattr(rag.config, "stream_chunk_chars", 32)
            for piece in iter_pseudo_tokens(answer, window=window):
                yield format_sse("token", {"text": piece})

            done_payload = {
                "answer": answer,
                "sources": sources,
                "session_id": sid,
                "stream_mode": STREAM_MODE,
                "generation_metrics": result.get("generation_metrics"),
                "constraint_checks": result.get("constraint_checks"),
                "retry_count": result.get("retry_count"),
                "repaired": result.get("repaired"),
                "top_k_applied": result.get("top_k_applied"),
                "top_k_mode": result.get("top_k_mode"),
            }
            yield format_sse("done", done_payload)
            elapsed_ms = (time.perf_counter() - started) * 1000
            qa_logger.log(
                request_id=request_id,
                query=body.query,
                status="ok",
                latency_ms=elapsed_ms,
                session_id=sid,
                code=0,
                top_k=body.top_k,
                n_sources=len(sources),
                extra={"session_created": created_new, "stream_mode": STREAM_MODE},
            )
        except AppException as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            qa_logger.log(
                request_id=request_id,
                query=body.query,
                status="error",
                latency_ms=elapsed_ms,
                session_id=sid,
                code=int(exc.code),
                top_k=body.top_k,
                error_detail=exc.detail,
                extra={"session_created": created_new, "stream_mode": STREAM_MODE},
            )
            yield format_sse(
                "error",
                {
                    "code": int(exc.code),
                    "message": exc.message,
                    "data": {"detail": exc.detail} if exc.detail is not None else None,
                    "request_id": request_id,
                    "timestamp": utc_now_iso(),
                    "session_id": sid,
                    "stream_mode": STREAM_MODE,
                },
            )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - started) * 1000
            qa_logger.log(
                request_id=request_id,
                query=body.query,
                status="error",
                latency_ms=elapsed_ms,
                session_id=sid,
                code=int(ErrorCode.INTERNAL_ERROR),
                top_k=body.top_k,
                error_detail=f"{type(exc).__name__}: {exc}",
                extra={"session_created": created_new, "stream_mode": STREAM_MODE},
            )
            yield format_sse(
                "error",
                {
                    "code": int(ErrorCode.INTERNAL_ERROR),
                    "message": ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR],
                    "data": {"error_type": type(exc).__name__, "detail": str(exc)},
                    "request_id": request_id,
                    "timestamp": utc_now_iso(),
                    "session_id": sid,
                    "stream_mode": STREAM_MODE,
                },
            )

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Stream-Mode": STREAM_MODE,
        },
    )


# NOTE: Do NOT register GET /api/v1/sessions/{id} here.
# Full session history lives in ``app.api.sessions`` (file-backed).
# Stage-11 used a preview-only route that would shadow it if included first.
