"""Medical RAG FastAPI — stage 12 shell (health/qa from 11; ops routers later)."""

from __future__ import annotations

from fastapi import FastAPI, Request

from app import __version__
from app.bootstrap import bootstrap_paths
from app.bridge11 import wire_stage11
from app.config import DEFAULT_CONFIG

bootstrap_paths()

app = FastAPI(
    title="Medical RAG API (Ops)",
    version=__version__,
    description=(
        "Stage 12 ops layer: sessions / stats / documents (upcoming) "
        "on stage-11 QA + health. "
        "Shared SessionStore / QACallLogger singletons with /qa."
    ),
    openapi_tags=[
        {"name": "health", "description": "Liveness / readiness (stage 11)"},
        {"name": "qa", "description": "Sync + pseudo-SSE QA (stage 11)"},
        {"name": "sessions", "description": "Session CRUD (stage 12 · upcoming)"},
        {"name": "stats", "description": "Ops statistics (stage 12 · upcoming)"},
        {"name": "documents", "description": "Document catalog (stage 12 · upcoming)"},
    ],
)

_S11 = wire_stage11(app)


@app.get("/")
def root(request: Request):
    s11_cfg = _S11["config"].DEFAULT_CONFIG
    request_id = getattr(getattr(request, "state", None), "request_id", None)
    return _S11["success_response"](
        {
            "service": "medical-rag-api",
            "version": __version__,
            "stage": "12-0",
            "retrieval_mode": s11_cfg.retrieval_mode,
            "pipeline_backend": s11_cfg.pipeline_backend,
            "documents_mode": DEFAULT_CONFIG.documents_mode,
            "singletons": "stage11-deps",
        },
        request_id=request_id,
    )
