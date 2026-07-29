"""Medical RAG FastAPI — stage 12 ops (sessions + stats + documents) + stage-11 QA."""

from __future__ import annotations

from fastapi import FastAPI, Request

from app import __version__
from app.api.documents import router as documents_router
from app.api.sessions import router as sessions_router
from app.api.stats import router as stats_router
from app.bootstrap import bootstrap_paths
from app.bridge11 import wire_stage11
from app.config import DEFAULT_CONFIG

bootstrap_paths()

app = FastAPI(
    title="Medical RAG API (Ops)",
    version=__version__,
    description=(
        "Stage 12 ops layer on stage-11 QA + health.\n\n"
        "**Capabilities**\n"
        "- Sessions CRUD (shared `MemorySessionStore` with `/qa`)\n"
        "- Ops stats: QA JSONL / index / component health\n"
        "- Documents catalog (`doc_id` = pmcid)\n\n"
        "**Error semantics**\n"
        "- `POST /qa`: invalid `session_id` → auto-create\n"
        "- `GET/DELETE /sessions/{id}` missing → **3002**\n"
        "- `GET /documents/{id}` missing → **3001**\n"
        "- Unmatched route HTTP 404 → business code **1001** (not 3001)\n\n"
        "Daily path uses **sample** retrieval + documents. "
        "Full-dataset simulation: `scripts/run_full_ops_smoke.py` / "
        "`api-ops-full.ipynb` F1+ (stage 5). Delivery: stage 6 report."
    ),
    openapi_tags=[
        {"name": "health", "description": "Liveness / readiness (stage 11)"},
        {"name": "qa", "description": "Sync + pseudo-SSE QA (stage 11)"},
        {
            "name": "sessions",
            "description": "Session CRUD — shared store with /qa; missing → 3002",
        },
        {
            "name": "stats",
            "description": "Ops statistics — qa_calls.jsonl / Chroma+docs / probes",
        },
        {
            "name": "documents",
            "description": "Read-only literature catalog; doc_id=pmcid; missing → 3001",
        },
    ],
)

_S11 = wire_stage11(app)  # drops stage-11 GET /sessions summary
app.include_router(sessions_router)
app.include_router(stats_router)
app.include_router(documents_router)


@app.get("/", tags=["health"], summary="Service root / capability banner")
def root(request: Request):
    """Return stage banner (`stage=12-6`) and capability flags."""
    s11_cfg = _S11["config"].DEFAULT_CONFIG
    request_id = getattr(getattr(request, "state", None), "request_id", None)
    return _S11["success_response"](
        {
            "service": "medical-rag-api",
            "version": __version__,
            "stage": "12-6",
            "retrieval_mode": s11_cfg.retrieval_mode,
            "pipeline_backend": s11_cfg.pipeline_backend,
            "documents_mode": DEFAULT_CONFIG.documents_mode,
            "singletons": "stage11-deps",
            "sessions": "crud",
            "stats": "qa+index+health",
            "documents": "catalog",
            "full_ops": "smoke",
            "delivery": "complete",
        },
        request_id=request_id,
    )
