"""Ops statistics API — QA JSONL / index / component health."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.config import DEFAULT_CONFIG
from app.deps import get_qa_logger
from app.schemas.stats import HealthStats, IndexStats, QAStats
from app.services.stats_service import (
    aggregate_qa_stats,
    collect_component_health,
    collect_index_stats,
)

router = APIRouter(tags=["stats"])


def _success(data: Any, request: Request):
    from app.schemas.response import success_response

    return success_response(
        data,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get(
    "/api/v1/stats/qa",
    response_model=None,
    summary="QA call aggregates",
    response_description="total_calls / success_rate / avg_latency_seconds",
)
def stats_qa(request: Request, qlog=Depends(get_qa_logger)):
    """Aggregate the shared ``qa_calls.jsonl`` (same path as ``POST /qa``).

    Latency in the log is **ms**; response exposes **seconds**.
    """
    stats: QAStats = aggregate_qa_stats(getattr(qlog, "path", None))
    return _success(stats.model_dump(), request)


@router.get(
    "/api/v1/stats/index",
    response_model=None,
    summary="Index scale (chunks vs documents)",
)
def stats_index(request: Request):
    """Chroma ``chunk_count`` + documents sqlite ``document_count`` (never confuse).

    ``incremental_update_count`` is MVP placeholder (=0).
    """
    stats: IndexStats = collect_index_stats(config=DEFAULT_CONFIG)
    return _success(stats.model_dump(), request)


@router.get(
    "/api/v1/stats/health",
    response_model=None,
    summary="Component health (llm / vector / database / api)",
)
def stats_health(request: Request):
    """llm←probe_ollama; vector←persist+count; database always ``skipped``; api=ok."""
    stats: HealthStats = collect_component_health(config=DEFAULT_CONFIG)
    return _success(stats.model_dump(), request)
