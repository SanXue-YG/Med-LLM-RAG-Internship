"""Ops statistics response models (stage 12)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QAStats(BaseModel):
    total_calls: int
    success_count: int
    failure_count: int
    success_rate: float = Field(description="success_count / total_calls; 0 when empty")
    avg_latency_seconds: float = Field(
        description="mean(latency_ms) / 1000; 0 when empty"
    )


class IndexStats(BaseModel):
    document_count: int | None = Field(
        default=None, description="documents sqlite COUNT(*) — not chunk count"
    )
    chunk_count: int | None = Field(
        default=None, description="Chroma collection.count() for retrieval_mode"
    )
    index_size_bytes: int | None = None
    incremental_update_count: int = 0
    note: str | None = None
    retrieval_mode: str | None = None
    documents_mode: str | None = None
    bm25_num_shards: int | None = None


class ComponentHealth(BaseModel):
    name: str  # llm | vector_db | database | api
    status: Literal["ok", "degraded", "down", "skipped"]
    detail: dict[str, Any] | None = None


class HealthStats(BaseModel):
    components: list[ComponentHealth]
