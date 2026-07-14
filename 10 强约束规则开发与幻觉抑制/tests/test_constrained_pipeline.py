"""Tests for ConstrainedGenerationPipeline (stage 4)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

STAGE10 = Path(__file__).resolve().parents[1]
SRC = STAGE10 / "src"
STAGE07 = STAGE10.parent / "07 生成模块与提示词工程第一部分" / "src"
STAGE08 = STAGE10.parent / "08 生成模块与提示词工程第二部分" / "src"


@pytest.fixture(autouse=True)
def _paths():
    for p in (STAGE07, STAGE08, SRC):
        sp = str(p.resolve())
        if sp not in sys.path:
            sys.path.insert(0, sp)
    for name in (
        "config",
        "citation_guard",
        "constraint_prompts",
        "format_checker",
        "constrained_pipeline",
    ):
        sys.modules.pop(name, None)
    from bootstrap import bootstrap_paths

    bootstrap_paths(STAGE10)
    yield


def _fixture_chunks():
    return [
        {
            "chunk_id": "PMC_A",
            "doc_id": "PMC_A",
            "source_title": "Metformin cardiovascular study",
            "text": "Metformin improves cardiovascular outcomes in type 2 diabetes.",
            "final_score": 0.9,
        },
        {
            "chunk_id": "PMC_B",
            "doc_id": "PMC_B",
            "source_title": "AMPK and fibrosis",
            "text": "AMPK activation reduces myocardial fibrosis.",
            "final_score": 0.8,
        },
    ]


GOOD_FINAL = (
    "**Answer:** Metformin may benefit cardiovascular risk [1]. "
    "AMPK-related mechanisms are discussed [2].\n\n"
    "**Evidence Summary:**\n"
    "- Cardiovascular outcomes with metformin [1]\n"
    "- AMPK and fibrosis [2]\n"
)

BAD_CITATION_FINAL = "**Answer:** Only invalid citation [99]."

REFUSAL_FINAL = "Based on the provided literature, this question cannot be answered."


class DummyRetrievalPipeline:
    def run(self, query: str) -> dict:
        return {
            "query": query,
            "retrieval": {"fused": _fixture_chunks()},
            "reranked": _fixture_chunks(),
        }


class ScriptedLLM:
    """Return scripted final answers; draft/review are minimal stubs."""

    def __init__(self, final_answers: list[str]) -> None:
        self._final_answers = list(final_answers)
        self._final_idx = 0
        self.final_calls = 0

    def generate_json(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return {
            "relevant_chunk_ids": ["PMC_A"],
            "excluded_chunk_ids": [],
            "notes": "ok",
        }

    def generate(self, prompt: str, **kwargs):  # noqa: ANN003
        system = kwargs.get("system_prompt") or ""
        blob = system + "\n" + prompt
        if "review comments" in blob.lower() or "revision suggestions" in blob.lower():
            return "- note uncertainty"
        if "Draft:\n" not in blob and "CORRECTION REQUIRED" not in blob:
            return "Draft from evidence."
        self.final_calls += 1
        idx = min(self._final_idx, len(self._final_answers) - 1)
        text = self._final_answers[idx]
        if self._final_idx < len(self._final_answers) - 1:
            self._final_idx += 1
        return text


def _make_pipeline(llm: ScriptedLLM, *, max_retries: int = 1):
    from config import Stage10Config
    from constrained_pipeline import ConstrainedGenerationPipeline
    from context_assembler import ContextAssembler

    cfg = Stage10Config(max_retries=max_retries)
    return ConstrainedGenerationPipeline(
        retrieval_pipeline=DummyRetrievalPipeline(),
        context_assembler=ContextAssembler(tokenizer_name=None),
        llm_generator=llm,
        config=cfg,
        skip_evidence_eval=True,
        skip_critical_review=True,
        run_optional_eval=True,
    )


def test_fixture_path_passes_constraints():
    pipe = _make_pipeline(ScriptedLLM([GOOD_FINAL]))
    result = pipe.run(
        "metformin cardiovascular effects",
        fixture_chunks=_fixture_chunks(),
    )
    assert result["constraint_checks"]["citation"]["ok"] is True
    assert result["constraint_checks"]["format"]["ok"] is True
    assert result["constraint_checks"]["boundary_hit"] is False
    assert result["retry_count"] == 0
    assert result["repaired"] is False
    assert "[1]" in result["labeled_context_preview"]
    assert result["optional_evaluation"]["hallucination_risk"] >= 0.0
    assert "Sources:" in result["answer"]


def test_retry_after_invalid_citation():
    pipe = _make_pipeline(ScriptedLLM([BAD_CITATION_FINAL, GOOD_FINAL]), max_retries=1)
    result = pipe.run("metformin effects", fixture_chunks=_fixture_chunks())
    assert result["retry_count"] == 1
    assert result["constraint_checks"]["citation"]["ok"] is True
    assert 99 not in result["constraint_checks"]["citation"]["extracted"]


def test_repair_when_retries_exhausted():
    pipe = _make_pipeline(ScriptedLLM([BAD_CITATION_FINAL]), max_retries=0)
    result = pipe.run("metformin effects", fixture_chunks=_fixture_chunks())
    assert result["retry_count"] == 0
    assert result["repaired"] is True
    assert "[99]" not in result["answer"]
    assert result["constraint_checks"]["citation"]["ok"] is True


def test_refusal_boundary_hit_exempts_format():
    pipe = _make_pipeline(ScriptedLLM([REFUSAL_FINAL]))
    result = pipe.run(
        "What is the latest FDA treatment in 2025?",
        fixture_chunks=_fixture_chunks(),
    )
    assert result["constraint_checks"]["boundary_hit"] is True
    assert result["constraint_checks"]["format"]["ok"] is True
    assert result["constraint_checks"]["citation"]["ok"] is True


def test_append_to_preserves_stage07_system():
    from constraint_prompts import default_constraint_bundle

    bundle = default_constraint_bundle()
    base = "You are a cautious medical assistant."
    merged = bundle.append_to(base)
    assert merged.startswith(base)
    assert "HARD CONSTRAINTS" in merged
