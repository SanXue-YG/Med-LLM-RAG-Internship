"""Dependency providers — reuse **stage-11 process singletons** for /qa alignment.

Sessions / stats / documents (stage 1+) must call these same factories so
``MemorySessionStore`` and ``qa_calls.jsonl`` stay shared with ``POST /api/v1/qa``.
"""

from __future__ import annotations

from app.bridge11 import load_stage11, reset_stage11_cache


def get_session_store():
    return load_stage11()["deps"].get_session_store()


def get_rag_service():
    return load_stage11()["deps"].get_rag_service()


def get_qa_logger():
    return load_stage11()["deps"].get_qa_logger()


def reset_singletons() -> None:
    """Test helper: clear stage-11 Depends cache + bridge cache."""
    s11 = load_stage11()
    s11["deps"].reset_singletons()
    reset_stage11_cache()
