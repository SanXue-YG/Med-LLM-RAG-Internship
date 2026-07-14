"""Stage 4: glue 08 generation with constraint injection and post-checks.

Flow:
  retrieve/assemble → assign_labels → append_to(system) per LLM step
  → generate → CitationGuard + FormatChecker → retry / repair
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

try:
    from .citation_guard import CitationGuard, CitationCheckResult, default_citation_guard
    from .config import DEFAULT_CONFIG, Stage10Config
    from .constraint_prompts import ConstraintPromptBundle, default_constraint_bundle
    from .format_checker import FormatCheckResult, FormatChecker, default_format_checker
except ImportError:
    from citation_guard import (  # type: ignore[no-redef]
        CitationGuard,
        CitationCheckResult,
        default_citation_guard,
    )
    from config import DEFAULT_CONFIG, Stage10Config  # type: ignore[no-redef]
    from constraint_prompts import (  # type: ignore[no-redef]
        ConstraintPromptBundle,
        default_constraint_bundle,
    )
    from format_checker import (  # type: ignore[no-redef]
        FormatCheckResult,
        FormatChecker,
        default_format_checker,
    )

DEFAULT_CONSTRAINTS = (
    "Use only provided context. "
    "Do not fabricate citations. "
    "State uncertainty when evidence is weak."
)
DEFAULT_OUTPUT_FORMAT = (
    "Plain text answer + short evidence bullets + uncertainty note."
)


@dataclass
class ConstraintChecks:
    """Aggregated post-generation constraint validation."""

    citation: dict[str, Any]
    format: dict[str, Any]
    boundary_hit: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation": self.citation,
            "format": self.format,
            "boundary_hit": self.boundary_hit,
        }


@dataclass
class ConstrainedGenerationResult:
    """08-compatible payload plus stage-10 constraint metadata."""

    query: str
    answer: str
    sources: list[dict[str, Any]]
    context_metadata: dict[str, Any]
    generation_metrics: dict[str, Any]
    intermediate_results: dict[str, Any]
    constraint_checks: ConstraintChecks
    retry_count: int = 0
    repaired: bool = False
    optional_evaluation: dict[str, Any] | None = None
    timestamp: str = ""
    labeled_context_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": self.query,
            "answer": self.answer,
            "sources": self.sources,
            "context_metadata": self.context_metadata,
            "generation_metrics": self.generation_metrics,
            "intermediate_results": self.intermediate_results,
            "constraint_checks": self.constraint_checks.to_dict(),
            "retry_count": self.retry_count,
            "repaired": self.repaired,
            "timestamp": self.timestamp,
        }
        if self.optional_evaluation is not None:
            payload["optional_evaluation"] = self.optional_evaluation
        if self.labeled_context_preview:
            payload["labeled_context_preview"] = self.labeled_context_preview
        return payload


class ConstrainedGenerationPipeline:
    """08 MedicalGenerationPipeline + stage-10 constraint layer."""

    def __init__(
        self,
        retrieval_pipeline: Any,
        context_assembler: Any,
        llm_generator: Any,
        *,
        config: Stage10Config | None = None,
        constraint_bundle: ConstraintPromptBundle | None = None,
        citation_guard: CitationGuard | None = None,
        format_checker: FormatChecker | None = None,
        skip_evidence_eval: bool = False,
        skip_critical_review: bool = False,
        max_context_tokens: int = 2048,
        run_optional_eval: bool = False,
    ) -> None:
        self.retrieval_pipeline = retrieval_pipeline
        self.context_assembler = context_assembler
        self.llm_generator = llm_generator
        self.config = config or DEFAULT_CONFIG
        self.bundle = constraint_bundle or default_constraint_bundle(self.config)
        self.citation_guard = citation_guard or default_citation_guard(self.config)
        self.format_checker = format_checker or default_format_checker(config=self.config)
        self.skip_evidence_eval = skip_evidence_eval
        self.skip_critical_review = skip_critical_review
        self.max_context_tokens = max_context_tokens
        self.run_optional_eval = run_optional_eval

    @classmethod
    def from_mode(
        cls,
        mode: str = "full",
        *,
        config: Stage10Config | None = None,
        skip_evidence_eval: bool = True,
        skip_critical_review: bool = True,
        max_context_tokens: int = 2048,
        run_optional_eval: bool = False,
        llm_timeout: float = 300.0,
    ) -> ConstrainedGenerationPipeline:
        """Bootstrap upstream 06/07/08 and return a full-corpus pipeline."""
        try:
            from bootstrap import OLLAMA_BASE_URL, OLLAMA_MODEL
        except ImportError:
            from bootstrap import OLLAMA_BASE_URL, OLLAMA_MODEL  # type: ignore[no-redef]

        from context_assembler import ContextAssembler
        from llm_generator import LLMGenerator
        from pipeline import RetrievalPipeline

        retrieval = RetrievalPipeline.from_mode(mode)
        assembler = ContextAssembler(tokenizer_name=None)
        llm = LLMGenerator(
            model_name=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            timeout=llm_timeout,
        )
        return cls(
            retrieval_pipeline=retrieval,
            context_assembler=assembler,
            llm_generator=llm,
            config=config,
            skip_evidence_eval=skip_evidence_eval,
            skip_critical_review=skip_critical_review,
            max_context_tokens=max_context_tokens,
            run_optional_eval=run_optional_eval,
        )

    def run(
        self,
        query: str,
        *,
        fixture_chunks: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Run constrained generation; return 08-compatible dict + constraint fields."""
        t_start = time.perf_counter()
        stage_times: dict[str, float] = {}
        stage_success: dict[str, bool] = {}
        token_counts: dict[str, int] = {}

        # 1) Retrieve + assemble (or fixture)
        t0 = time.perf_counter()
        if fixture_chunks is not None:
            assembled = self.context_assembler.assemble(
                fixture_chunks,
                max_context_tokens=self.max_context_tokens,
            )
        else:
            retrieval_result = self.retrieval_pipeline.run(query)
            candidates = retrieval_result.get("reranked") or retrieval_result["retrieval"]["fused"]
            assembled = self.context_assembler.assemble(
                candidates,
                max_context_tokens=self.max_context_tokens,
            )

        selected_chunks: list[Any] = list(assembled.selected_chunks)
        labeled = self.citation_guard.assign_labels(selected_chunks)
        current_context = labeled.context_text
        valid_ids = labeled.valid_ids
        selected_chunks = list(labeled.selected_chunks)
        stage_times["assemble"] = _elapsed(t0)
        stage_success["assemble"] = True
        token_counts["context_estimated"] = self.context_assembler.estimate_tokens(current_context)

        evidence_evaluation: dict[str, Any] | None = None
        review_feedback = ""

        # 2) Evidence evaluation (optional)
        if not self.skip_evidence_eval:
            t1 = time.perf_counter()
            try:
                from json_utils import normalize_evidence_evaluation
                from prompts import render_prompt_stage

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
                    system_prompt=self._constrained_system(eval_payload["system_prompt"]),
                    temperature=eval_payload["temperature"],
                    max_tokens=eval_payload["max_tokens"],
                    think=False,
                )
                evidence_evaluation = normalize_evidence_evaluation(evidence_evaluation)
                from json_utils import filter_chunks_by_evidence_eval

                selected_chunks = filter_chunks_by_evidence_eval(
                    selected_chunks, evidence_evaluation
                )
                labeled = self.citation_guard.assign_labels(selected_chunks)
                current_context = labeled.context_text
                valid_ids = labeled.valid_ids
                selected_chunks = list(labeled.selected_chunks)
                stage_success["evidence_eval"] = True
            except Exception:
                stage_success["evidence_eval"] = False
            stage_times["evidence_eval"] = _elapsed(t1)
        else:
            stage_success["evidence_eval"] = True
            stage_times["evidence_eval"] = 0.0

        # 3) Draft
        t2 = time.perf_counter()
        from prompts import render_prompt_stage

        draft_payload = render_prompt_stage(
            "answer_generator",
            question=query,
            context=current_context,
            constraints=DEFAULT_CONSTRAINTS,
            output_format=DEFAULT_OUTPUT_FORMAT,
        )
        draft_answer = self.llm_generator.generate(
            draft_payload["user_prompt"],
            system_prompt=self._constrained_system(draft_payload["system_prompt"]),
            temperature=draft_payload["temperature"],
            max_tokens=draft_payload["max_tokens"],
            think=False,
        )
        stage_times["draft"] = _elapsed(t2)
        stage_success["draft"] = bool((draft_answer or "").strip())
        token_counts["draft_estimated"] = max(1, len(draft_answer or "") // 4)

        # 4) Critical review (optional)
        if not self.skip_critical_review:
            t3 = time.perf_counter()
            review_payload = render_prompt_stage(
                "critical_reviewer",
                question=query,
                context=current_context,
                constraints=(
                    DEFAULT_CONSTRAINTS + "\nDraft answer:\n" + (draft_answer or "")
                ),
                output_format="Bullet list of risks and revision suggestions.",
            )
            review_feedback = self.llm_generator.generate(
                review_payload["user_prompt"],
                system_prompt=self._constrained_system(review_payload["system_prompt"]),
                temperature=review_payload["temperature"],
                max_tokens=review_payload["max_tokens"],
                think=False,
            )
            stage_times["review"] = _elapsed(t3)
            stage_success["review"] = bool((review_feedback or "").strip())
        else:
            stage_times["review"] = 0.0
            stage_success["review"] = True

        # 5) Final answer + constraint retry loop
        t4 = time.perf_counter()
        final_constraints = DEFAULT_CONSTRAINTS + "\nDraft:\n" + (draft_answer or "")
        if (review_feedback or "").strip():
            final_constraints += "\nReviewer feedback:\n" + review_feedback

        retry_count = 0
        repaired = False
        correction_hint = ""
        final_answer = ""
        citation_check = CitationCheckResult(ok=True, valid_ids=valid_ids)
        format_check = FormatCheckResult(ok=True)
        boundary_hit = False

        max_attempts = 1 + max(0, self.config.max_retries)
        for attempt in range(max_attempts):
            attempt_constraints = final_constraints
            if correction_hint:
                attempt_constraints += f"\n\nCORRECTION REQUIRED:\n{correction_hint}"

            final_payload = render_prompt_stage(
                "final_assembler",
                question=query,
                context=current_context,
                constraints=attempt_constraints,
                output_format=DEFAULT_OUTPUT_FORMAT,
            )
            final_answer = self.llm_generator.generate(
                final_payload["user_prompt"],
                system_prompt=self._constrained_system(final_payload["system_prompt"]),
                temperature=final_payload["temperature"],
                max_tokens=final_payload["max_tokens"],
                think=False,
            )

            from postprocess import format_sources, postprocess_answer

            sources = format_sources(selected_chunks)
            candidate_answer = postprocess_answer(final_answer or "", sources)

            boundary_hit, citation_check, format_check, needs_retry = _evaluate_constraints(
                self.citation_guard,
                self.format_checker,
                candidate_answer,
                valid_ids,
                sources=sources,
            )

            if not needs_retry:
                final_answer = candidate_answer
                break

            if attempt < max_attempts - 1:
                retry_count += 1
                correction_hint = _build_correction_hint(
                    self.citation_guard, citation_check, format_check
                )
                continue

            # Exhausted retries — conservative repair
            repaired_answer = candidate_answer
            if citation_check.issues or citation_check.invalid:
                repaired_answer, did_repair = self.citation_guard.retry_or_repair(
                    repaired_answer,
                    citation_check,
                )
                repaired = repaired or did_repair
            patched_answer, did_patch = self.format_checker.soft_patch(
                repaired_answer, format_check
            )
            repaired = repaired or did_patch
            final_answer = patched_answer

            boundary_hit, citation_check, format_check, _ = _evaluate_constraints(
                self.citation_guard,
                self.format_checker,
                final_answer,
                valid_ids,
                sources=sources,
            )
            break

        stage_times["final"] = _elapsed(t4)
        stage_success["final"] = bool((final_answer or "").strip())

        # 6) Postprocess metrics (sources already built in loop)
        t5 = time.perf_counter()
        from postprocess import format_sources

        sources = format_sources(selected_chunks)
        stage_times["postprocess"] = _elapsed(t5)
        stage_success["postprocess"] = True

        optional_evaluation = None
        if self.run_optional_eval:
            optional_evaluation = _optional_hallucination_eval(final_answer)

        checks = ConstraintChecks(
            citation=citation_check.to_dict(),
            format=format_check.to_dict(),
            boundary_hit=boundary_hit,
        )

        result = ConstrainedGenerationResult(
            query=query,
            answer=final_answer,
            sources=sources,
            context_metadata=assembled.metadata.to_dict(),
            generation_metrics={
                "total_time_seconds": round(time.perf_counter() - t_start, 3),
                "stage_times": stage_times,
                "token_counts": token_counts,
                "stage_success": stage_success,
                "constraint_attempts": 1 + retry_count,
            },
            intermediate_results={
                "evidence_evaluation": evidence_evaluation,
                "draft_answer": draft_answer,
                "review_feedback": review_feedback,
                "valid_citation_ids": sorted(valid_ids),
            },
            constraint_checks=checks,
            retry_count=retry_count,
            repaired=repaired,
            optional_evaluation=optional_evaluation,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            labeled_context_preview=_preview_text(current_context, limit=400),
        )
        return result.to_dict()

    def _constrained_system(self, base_system: str) -> str:
        return self.bundle.append_to(base_system)


def _evaluate_constraints(
    citation_guard: CitationGuard,
    format_checker: FormatChecker,
    answer: str,
    valid_ids: set[int],
    sources: list[dict[str, Any]] | None = None,
) -> tuple[bool, CitationCheckResult, FormatCheckResult, bool]:
    boundary_hit = format_checker.detect_boundary_hit(answer)
    citation_check = citation_guard.validate(
        answer, valid_ids, boundary_hit=boundary_hit
    )
    format_check = format_checker.check(
        answer, sources=sources, boundary_hit=boundary_hit
    )
    needs_retry = bool(citation_check.issues) or bool(format_check.issues)
    return boundary_hit, citation_check, format_check, needs_retry


def _build_correction_hint(
    citation_guard: CitationGuard,
    citation_check: CitationCheckResult,
    format_check: FormatCheckResult,
) -> str:
    parts: list[str] = []
    if citation_check.issues or citation_check.invalid:
        parts.append(citation_guard.build_retry_hint(citation_check))
    if format_check.issues:
        parts.append("Format validation failed. Fix these issues:")
        parts.extend(f"- {issue}" for issue in format_check.issues)
    return "\n".join(parts)


def _optional_hallucination_eval(answer: str) -> dict[str, Any]:
    try:
        from answer_evaluator import AnswerEvaluator

        risk, signals = AnswerEvaluator().detect_hallucination_signals(answer)
        return {
            "hallucination_risk": risk,
            "hallucination_signals": signals,
        }
    except Exception as exc:  # noqa: BLE001 — optional hook must not break pipeline
        return {"error": str(exc)}


def _preview_text(text: str, *, limit: int = 400) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "\n...[truncated]"


def _elapsed(start: float) -> float:
    return round(time.perf_counter() - start, 3)
