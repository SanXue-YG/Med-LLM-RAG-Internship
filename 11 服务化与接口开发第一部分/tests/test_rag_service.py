"""RagService unit tests (mock pipeline — no Ollama / corpus)."""

from __future__ import annotations

import httpx
import pytest

from app.config import Stage11Config
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.services.rag_service import RagService
from app.services.session_store import SessionTurn
from app.state import RUNTIME


class _FakeRetrieval:
    def __init__(self) -> None:
        self.top_k_final = 10


class _FakePipeline:
    def __init__(self) -> None:
        self.retrieval_pipeline = _FakeRetrieval()
        self.calls: list[str] = []

    def run(self, query: str, **kwargs):
        self.calls.append(query)
        return {
            "answer": f"ans:{query[:40]}",
            "sources": [{"index": i, "chunk_id": f"c{i}"} for i in range(1, 8)],
            "constraint_checks": {"boundary_hit": False},
            "generation_metrics": {},
        }


class _BoomHttpPipeline:
    retrieval_pipeline = _FakeRetrieval()

    def run(self, query: str, **kwargs):
        raise httpx.ConnectError("ollama down")


class _BoomOtherPipeline:
    retrieval_pipeline = _FakeRetrieval()

    def run(self, query: str, **kwargs):
        raise RuntimeError("unexpected")


@pytest.fixture(autouse=True)
def _reset_runtime():
    RUNTIME.pipeline_loaded = False
    RUNTIME.pipeline_mode = None
    RUNTIME.pipeline_backend = None
    RUNTIME.last_error = None
    yield


def test_answer_with_mock_sets_top_k_final():
    pipe = _FakePipeline()
    svc = RagService(Stage11Config(), pipeline=pipe)
    out = svc.answer("metformin effects", top_k=3)
    assert out["answer"].startswith("ans:")
    assert out["top_k_applied"] == 3
    assert out["top_k_mode"] == "retrieval.top_k_final"
    assert pipe.retrieval_pipeline.top_k_final == 10  # restored
    assert RUNTIME.pipeline_loaded is True


def test_answer_truncates_when_no_top_k_final():
    class NoTopK:
        def run(self, query: str, **kwargs):
            return {
                "answer": "x",
                "sources": [{"index": i} for i in range(10)],
                "generation_metrics": {},
            }

    svc = RagService(pipeline=NoTopK())
    out = svc.answer("q", top_k=4)
    assert len(out["sources"]) == 4
    assert out["top_k_mode"] == "truncate_sources"
    assert out["generation_metrics"].get("top_k_truncated") is True


def test_session_history_prefix_injected():
    pipe = _FakePipeline()
    svc = RagService(pipeline=pipe, inject_history=True)
    history = [SessionTurn(query="old q", answer="old a")]
    out = svc.answer("new q", session_history=history)
    assert "Conversation context" in pipe.calls[0]
    assert "new q" in pipe.calls[0]
    assert out["query"] == "new q"
    assert "Conversation context" in out["effective_query"]


def test_http_error_maps_to_4001():
    svc = RagService(pipeline=_BoomHttpPipeline())
    with pytest.raises(AppException) as ei:
        svc.answer("q")
    assert ei.value.code == ErrorCode.MODEL_CALL_FAILED


def test_other_error_maps_to_4002():
    svc = RagService(pipeline=_BoomOtherPipeline())
    with pytest.raises(AppException) as ei:
        svc.answer("q")
    assert ei.value.code == ErrorCode.PIPELINE_FAILED


def test_empty_query_1001():
    svc = RagService(pipeline=_FakePipeline())
    with pytest.raises(AppException) as ei:
        svc.answer("   ")
    assert ei.value.code == ErrorCode.PARAM_ERROR


def test_top_k_out_of_range_1001():
    svc = RagService(pipeline=_FakePipeline())
    with pytest.raises(AppException) as ei:
        svc.answer("q", top_k=999)
    assert ei.value.code == ErrorCode.PARAM_ERROR
