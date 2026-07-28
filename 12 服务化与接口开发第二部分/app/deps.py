"""Dependency providers — reuse **stage-11 process singletons** for /qa alignment.

Sessions / stats / documents (stage 1+) must call these same factories so
``MemorySessionStore`` and ``qa_calls.jsonl`` stay shared with ``POST /api/v1/qa``.
"""

from __future__ import annotations

from app.bridge11 import load_stage11
from app.config import DEFAULT_CONFIG
from app.services.document_store import DocumentStore


def get_session_store():
    return load_stage11()["deps"].get_session_store()


def get_rag_service():
    return load_stage11()["deps"].get_rag_service()


def get_qa_logger():
    return load_stage11()["deps"].get_qa_logger()


def get_document_store() -> DocumentStore:
    """Read-only catalog; mode from ``STAGE12_DOCUMENTS_MODE`` (default sample)."""
    return DocumentStore(mode=DEFAULT_CONFIG.documents_mode)  # type: ignore[arg-type]


def reset_singletons() -> None:
    """Test/notebook helper: clear stage-11 ``lru_cache`` Depends only.

    Does **not** clear ``bridge11`` cache — after ``app.main`` is imported the
    QA router already closed over the wired ``deps`` callables; clearing the
    bridge would make overrides miss those objects (sessions vs /qa split).
    """
    s11 = load_stage11()
    s11["deps"].reset_singletons()
