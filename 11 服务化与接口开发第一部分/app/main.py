"""Medical RAG FastAPI application (stage 5: delivered sync + pseudo-SSE QA)."""

from __future__ import annotations

from fastapi import FastAPI, Request

from app import __version__
from app.api.health import router as health_router
from app.api.qa import router as qa_router
from app.config import DEFAULT_CONFIG
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestContextMiddleware
from app.schemas.response import success_response

setup_logging(DEFAULT_CONFIG)
logger = get_logger("main")

app = FastAPI(
    title="Medical RAG API",
    version=__version__,
    description=(
        "Stage 11 Medical RAG HTTP API. "
        "Sync POST /api/v1/qa; pseudo-SSE POST /api/v1/qa/stream "
        "(stream_mode=pseudo — not live Ollama tokens)."
    ),
)

app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(qa_router)


@app.get("/")
def root(request: Request):
    return success_response(
        {
            "service": "medical-rag-api",
            "version": __version__,
            "stage": "5-done",
            "retrieval_mode": DEFAULT_CONFIG.retrieval_mode,
            "pipeline_backend": DEFAULT_CONFIG.pipeline_backend,
        },
        request_id=request.state.request_id,
    )


logger.info(
    "app_created version=%s retrieval_mode=%s backend=%s",
    __version__,
    DEFAULT_CONFIG.retrieval_mode,
    DEFAULT_CONFIG.pipeline_backend,
)
