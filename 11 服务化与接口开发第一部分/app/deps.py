"""FastAPI dependency providers (process singletons)."""

from __future__ import annotations

from functools import lru_cache

from app.config import DEFAULT_CONFIG
from app.services.qa_logger import QACallLogger
from app.services.rag_service import RagService
from app.services.session_store import MemorySessionStore


@lru_cache(maxsize=1)
def get_session_store() -> MemorySessionStore:
    return MemorySessionStore(DEFAULT_CONFIG)


@lru_cache(maxsize=1)
def get_rag_service() -> RagService:
    return RagService(DEFAULT_CONFIG)


@lru_cache(maxsize=1)
def get_qa_logger() -> QACallLogger:
    return QACallLogger(DEFAULT_CONFIG)


def reset_singletons() -> None:
    """Test helper: clear cached Depends providers."""
    get_session_store.cache_clear()
    get_rag_service.cache_clear()
    get_qa_logger.cache_clear()
