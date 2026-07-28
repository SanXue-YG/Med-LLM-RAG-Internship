"""Document catalog response models (stage 12). ``doc_id`` == ``pmcid``."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    """Read-only literature metadata row (menu / catalog)."""

    doc_id: str = Field(description="pmcid (primary key)")
    title: str
    abstract: str | None = None
    journal: str | None = None
    pub_date: str | None = None
    pmid: str | None = None
    pub_year: int | None = None
