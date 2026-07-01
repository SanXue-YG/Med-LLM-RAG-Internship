import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
STAGE07_SRC = Path(__file__).resolve().parents[2] / "07 生成模块与提示词工程第一部分" / "src"
sys.path.insert(0, str(STAGE07_SRC))
sys.path.insert(0, str(SRC))

from context_assembler import ContextAssembler  # noqa: E402
from generation_pipeline import MedicalGenerationPipeline  # noqa: E402


class DummyRetrievalPipeline:
    def run(self, query: str) -> dict:
        return {
            "query": query,
            "retrieval": {"fused": []},
            "reranked": [
                {
                    "chunk_id": "PMC_A",
                    "doc_id": "PMC_A",
                    "source_title": "Study A",
                    "text": "Metformin improves glycemic control in type 2 diabetes.",
                    "final_score": 0.9,
                },
                {
                    "chunk_id": "PMC_B",
                    "doc_id": "PMC_B",
                    "source_title": "Study B",
                    "text": "Evidence on cardiovascular benefit is moderate.",
                    "final_score": 0.8,
                },
            ],
        }


class DummyLLM:
    def generate_json(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return {
            "relevant_chunk_ids": ["PMC_A"],
            "excluded_chunk_ids": [],
            "notes": "Prefer chunk A",
        }

    def generate(self, prompt: str, **kwargs):  # noqa: ANN003
        if "review comments" in prompt.lower():
            return "- add caveat"
        if "Draft:" in prompt:
            return "Final grounded answer."
        return "Draft answer from evidence."


def test_pipeline_minimal_path_skip_optional():
    pipe = MedicalGenerationPipeline(
        retrieval_pipeline=DummyRetrievalPipeline(),
        context_assembler=ContextAssembler(tokenizer_name=None),
        llm_generator=DummyLLM(),
        skip_evidence_eval=True,
        skip_critical_review=True,
    )
    result = pipe.run("What is metformin used for?")
    assert result["query"] == "What is metformin used for?"
    assert result["intermediate_results"]["evidence_evaluation"] is None
    assert result["intermediate_results"]["draft_answer"]
    assert result["generation_metrics"]["stage_success"]["final"] is True
    assert len(result["sources"]) >= 1
    assert "Sources:" in result["answer"]
    assert "Medical disclaimer:" in result["answer"]


def test_pipeline_with_optional_stages():
    pipe = MedicalGenerationPipeline(
        retrieval_pipeline=DummyRetrievalPipeline(),
        context_assembler=ContextAssembler(tokenizer_name=None),
        llm_generator=DummyLLM(),
        skip_evidence_eval=False,
        skip_critical_review=False,
    )
    result = pipe.run("metformin cardiovascular effects")
    eval_obj = result["intermediate_results"]["evidence_evaluation"]
    assert eval_obj is not None
    assert eval_obj["relevant_chunk_ids"] == ["PMC_A"]
    assert result["generation_metrics"]["stage_success"]["evidence_eval"] is True
    assert result["generation_metrics"]["stage_success"]["review"] is True
    # 评估后应优先保留 chunk A
    assert result["sources"][0]["chunk_id"] == "PMC_A"
    assert "[1]" in result["answer"]
