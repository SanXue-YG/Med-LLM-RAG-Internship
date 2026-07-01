"""阶段 3：医学生成主流程（retrieve -> assemble -> generate）。"""

from __future__ import annotations

import time
from typing import Any

from json_utils import (
    filter_chunks_by_evidence_eval,
    normalize_evidence_evaluation,
)
from llm_generator import LLMGenerator
from postprocess import format_sources, postprocess_answer
from prompts import render_prompt_stage

DEFAULT_CONSTRAINTS = (
    "Use only provided context. "
    "Do not fabricate citations. "
    "State uncertainty when evidence is weak."
)
DEFAULT_OUTPUT_FORMAT = (
    "Plain text answer + short evidence bullets + uncertainty note."
)


class MedicalGenerationPipeline:
    """串联 06/07/08 的端到端生成流水线。"""

    def __init__(
        self,
        retrieval_pipeline: Any,
        context_assembler: Any,
        llm_generator: LLMGenerator,
        *,
        skip_evidence_eval: bool = False,
        skip_critical_review: bool = False,
        max_context_tokens: int = 2048,
    ) -> None:
        self.retrieval_pipeline = retrieval_pipeline
        self.context_assembler = context_assembler
        self.llm_generator = llm_generator
        self.skip_evidence_eval = skip_evidence_eval
        self.skip_critical_review = skip_critical_review
        self.max_context_tokens = max_context_tokens

    def run(self, query: str) -> dict[str, Any]:
        t_start = time.perf_counter()
        stage_times: dict[str, float] = {}
        stage_success: dict[str, bool] = {}
        token_counts: dict[str, int] = {}

        # 1) 检索 + 组装
        t0 = time.perf_counter()
        retrieval_result = self.retrieval_pipeline.run(query)
        candidates = retrieval_result.get("reranked") or retrieval_result["retrieval"]["fused"]
        assembled = self.context_assembler.assemble(
            candidates,
            max_context_tokens=self.max_context_tokens,
        )
        current_context = assembled.context_text
        selected_chunks: list[Any] = list(assembled.selected_chunks)
        stage_times["assemble"] = _elapsed(t0)
        stage_success["assemble"] = True
        token_counts["context_estimated"] = self.context_assembler.estimate_tokens(current_context)

        evidence_evaluation: dict[str, Any] | None = None
        review_feedback = ""

        # 2) 证据评估（可选）
        if not self.skip_evidence_eval:
            t1 = time.perf_counter()
            try:
                eval_payload = render_prompt_stage(
                    "evidence_evaluator",
                    question=query,
                    context=current_context,
                    constraints=DEFAULT_CONSTRAINTS,
                    output_format=(
                        '{"relevant_chunk_ids":[],"excluded_chunk_ids":[],"notes":""}'
                    ),
                )
                evidence_evaluation = self.llm_generator.generate_json(
                    eval_payload["user_prompt"],
                    system_prompt=eval_payload["system_prompt"],
                    temperature=eval_payload["temperature"],
                    max_tokens=eval_payload["max_tokens"],
                    think=False,
                )
                evidence_evaluation = normalize_evidence_evaluation(evidence_evaluation)
                selected_chunks = filter_chunks_by_evidence_eval(selected_chunks, evidence_evaluation)
                current_context = self._build_context_from_chunks(selected_chunks, fallback=current_context)
                stage_success["evidence_eval"] = True
            except Exception:
                # 降级：不筛选，继续后续流程
                stage_success["evidence_eval"] = False
            stage_times["evidence_eval"] = _elapsed(t1)
        else:
            stage_success["evidence_eval"] = True
            stage_times["evidence_eval"] = 0.0

        # 3) 生成草稿
        t2 = time.perf_counter()
        draft_payload = render_prompt_stage(
            "answer_generator",
            question=query,
            context=current_context,
            constraints=DEFAULT_CONSTRAINTS,
            output_format=DEFAULT_OUTPUT_FORMAT,
        )
        draft_answer = self.llm_generator.generate(
            draft_payload["user_prompt"],
            system_prompt=draft_payload["system_prompt"],
            temperature=draft_payload["temperature"],
            max_tokens=draft_payload["max_tokens"],
            think=False,
        )
        stage_times["draft"] = _elapsed(t2)
        stage_success["draft"] = bool(draft_answer.strip())
        token_counts["draft_estimated"] = max(1, len(draft_answer) // 4)

        # 4) 批判审查（可选）
        if not self.skip_critical_review:
            t3 = time.perf_counter()
            review_payload = render_prompt_stage(
                "critical_reviewer",
                question=query,
                context=current_context,
                constraints=(
                    DEFAULT_CONSTRAINTS
                    + "\nDraft answer:\n"
                    + draft_answer
                ),
                output_format="Bullet list of risks and revision suggestions.",
            )
            review_feedback = self.llm_generator.generate(
                review_payload["user_prompt"],
                system_prompt=review_payload["system_prompt"],
                temperature=review_payload["temperature"],
                max_tokens=review_payload["max_tokens"],
                think=False,
            )
            stage_times["review"] = _elapsed(t3)
            stage_success["review"] = bool(review_feedback.strip())
        else:
            stage_times["review"] = 0.0
            stage_success["review"] = True

        # 5) 最终答案组装
        t4 = time.perf_counter()
        final_constraints = DEFAULT_CONSTRAINTS + "\nDraft:\n" + draft_answer
        if review_feedback.strip():
            final_constraints += "\nReviewer feedback:\n" + review_feedback
        final_payload = render_prompt_stage(
            "final_assembler",
            question=query,
            context=current_context,
            constraints=final_constraints,
            output_format=DEFAULT_OUTPUT_FORMAT,
        )
        final_answer = self.llm_generator.generate(
            final_payload["user_prompt"],
            system_prompt=final_payload["system_prompt"],
            temperature=final_payload["temperature"],
            max_tokens=final_payload["max_tokens"],
            think=False,
        )
        stage_times["final"] = _elapsed(t4)
        stage_success["final"] = bool(final_answer.strip())

        # 6) 后处理（阶段 4 将进一步增强）
        t5 = time.perf_counter()
        sources = format_sources(selected_chunks)
        postprocessed_answer = postprocess_answer(final_answer, sources)
        stage_times["postprocess"] = _elapsed(t5)
        stage_success["postprocess"] = True

        result = {
            "query": query,
            "answer": postprocessed_answer,
            "context_metadata": assembled.metadata.to_dict(),
            "generation_metrics": {
                "total_time_seconds": round(time.perf_counter() - t_start, 3),
                "stage_times": stage_times,
                "token_counts": token_counts,
                "stage_success": stage_success,
            },
            "intermediate_results": {
                "evidence_evaluation": evidence_evaluation,
                "draft_answer": draft_answer,
                "review_feedback": review_feedback,
            },
            "sources": sources,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return result

    def _build_context_from_chunks(self, chunks: list[Any], *, fallback: str) -> str:
        texts = [_chunk_text(c) for c in chunks if _chunk_text(c).strip()]
        if not texts:
            return fallback
        return "\n\n".join(texts)

def _chunk_text(chunk: Any) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("text") or "")
    return str(getattr(chunk, "text", "") or "")


def _elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 3)
