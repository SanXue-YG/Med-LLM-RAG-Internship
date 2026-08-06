"""Med-RAG FastAPI — unified QA + sessions/stats/documents + ingest."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.documents import router as documents_router
from app.api.docs_content import router as docs_content_router
from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.qa import router as qa_router
from app.api.sessions import router as sessions_router
from app.api.stats import router as stats_router
from app.bootstrap import bootstrap_paths
from app.config import DEFAULT_CONFIG
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestContextMiddleware
from app.schemas.response import success_response

bootstrap_paths()
setup_logging(DEFAULT_CONFIG)
logger = get_logger("main")

app = FastAPI(
    title="Med-RAG API",
    version=__version__,
    description=(
        "Self-contained Medical RAG demo package.\n\n"
        "**Capabilities**\n"
        "- Sync POST /api/v1/qa + pseudo-SSE /qa/stream\n"
        "- Sessions CRUD + list/search (file store under data/chat)\n"
        "- Ops stats / documents catalog\n"
        "- Ingest upload for empty-index bootstrap & corpus updates\n"
    ),
    openapi_tags=[
        {"name": "health", "description": "Liveness / readiness / index probe"},
        {"name": "qa", "description": "Sync + pseudo-SSE QA"},
        {"name": "sessions", "description": "Session CRUD + list; missing → 3002"},
        {"name": "stats", "description": "QA JSONL / index / component health"},
        {"name": "documents", "description": "Literature catalog; doc_id=pmcid"},
        {"name": "ingest", "description": "Upload & index additional corpus"},
    ],
)

origins = [o.strip() for o in DEFAULT_CONFIG.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)

app.include_router(health_router)
app.include_router(qa_router)
app.include_router(sessions_router)
app.include_router(stats_router)
app.include_router(documents_router)
app.include_router(ingest_router)
app.include_router(docs_content_router)


@app.get("/", tags=["health"], summary="Service root / capability banner")
def root(request: Request):
    from paths import index_ready

    request_id = getattr(getattr(request, "state", None), "request_id", None)
    idx = index_ready(DEFAULT_CONFIG.retrieval_mode)
    return success_response(
        {
            "service": "med-rag-api",
            "version": __version__,
            "stage": "med-rag-pack",
            "retrieval_mode": DEFAULT_CONFIG.retrieval_mode,
            "pipeline_backend": DEFAULT_CONFIG.pipeline_backend,
            "documents_mode": DEFAULT_CONFIG.documents_mode,
            "sessions": "file-backed",
            "index": idx,
            "delivery": "demo",
        },
        request_id=request_id,
    )


logger.info(
    "app_created version=%s retrieval_mode=%s backend=%s",
    __version__,
    DEFAULT_CONFIG.retrieval_mode,
    DEFAULT_CONFIG.pipeline_backend,
)
