"""FastAPI dependency providers (process singletons)."""

from __future__ import annotations

from functools import lru_cache

from app.config import DEFAULT_CONFIG
from app.services.document_store import DocumentStore
from app.services.qa_logger import QACallLogger
from app.services.rag_service import RagService
from app.services.session_store import FileSessionStore


@lru_cache(maxsize=1)
def get_session_store() -> FileSessionStore:
    return FileSessionStore(DEFAULT_CONFIG)


@lru_cache(maxsize=1)
def get_rag_service() -> RagService:
    return RagService(DEFAULT_CONFIG)


@lru_cache(maxsize=1)
def get_qa_logger() -> QACallLogger:
    return QACallLogger(DEFAULT_CONFIG)


def get_document_store() -> DocumentStore:
    return DocumentStore(mode=DEFAULT_CONFIG.documents_mode)  # type: ignore[arg-type]


def reset_singletons() -> None:
    get_session_store.cache_clear()
    get_rag_service.cache_clear()
    get_qa_logger.cache_clear()
