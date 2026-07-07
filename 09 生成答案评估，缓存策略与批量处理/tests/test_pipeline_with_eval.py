from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from answer_evaluator import AnswerEvaluator
from generation_cache import GenerationCache
from model_adapter import GenerationRequest, GenerationResponse
from pipeline_with_eval import PipelineWithEval


class FakeAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.calls += 1
        return GenerationResponse(
            answer=f"answer for {request.query}",
            sources=[{"doc_id": "PMC1"}],
            model_name=request.model_name or "fake-model",
            provider="fake",
            raw={"answer": f"answer for {request.query}", "sources": [{"doc_id": "PMC1"}]},
        )


def _gt() -> dict:
    return {
        "reference_answer": "answer for q1",
        "key_phrases": ["answer", "q1"],
    }


def test_run_with_cache_and_eval_miss_then_hit() -> None:
    adapter = FakeAdapter()
    pipe = PipelineWithEval(
        model_adapter=adapter,
        evaluator=AnswerEvaluator(),
        cache=GenerationCache(ttl_seconds=60),
        provider="fake",
        default_model_name="fake-model",
    )

    first = pipe.run_with_cache_and_eval("q1", ground_truth_entry=_gt(), context_text="ctx", temperature=0.2)
    second = pipe.run_with_cache_and_eval("q1", ground_truth_entry=_gt(), context_text="ctx", temperature=0.2)

    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert adapter.calls == 1
    assert "evaluation" in second


def test_run_with_force_refresh_bypasses_cache() -> None:
    adapter = FakeAdapter()
    pipe = PipelineWithEval(
        model_adapter=adapter,
        evaluator=AnswerEvaluator(),
        cache=GenerationCache(ttl_seconds=60),
        provider="fake",
        default_model_name="fake-model",
    )
    _ = pipe.run_with_cache_and_eval("q2", ground_truth_entry=_gt(), context_text="ctx", temperature=0.2)
    _ = pipe.run_with_cache_and_eval(
        "q2",
        ground_truth_entry=_gt(),
        context_text="ctx",
        temperature=0.2,
        force_refresh=True,
    )
    assert adapter.calls == 2

