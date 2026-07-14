"""Stage 5 CLI: run adversarial evaluation and export report.

Examples:
    python scripts/run_adversarial_eval.py --mock
    python scripts/run_adversarial_eval.py --mode live --retrieval-mode full --fixture-only
    python scripts/run_adversarial_eval.py --mode live --retrieval-mode full --check-only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

STAGE10 = Path(__file__).resolve().parents[1]
SRC = STAGE10 / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stage-10 adversarial evaluation.")
    parser.add_argument(
        "--mode",
        choices=("fixture", "live"),
        default="fixture",
        help="fixture=use case fixture_chunks; live=real retrieval when no fixture",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use scripted answers (no Ollama). Implies fixture chunks from JSON.",
    )
    parser.add_argument(
        "--retrieval-mode",
        choices=("sample", "full"),
        default="full",
        help="Live pipeline retrieval mode (ConstrainedGenerationPipeline.from_mode)",
    )
    parser.add_argument(
        "--fixture-only",
        action="store_true",
        help="Only run cases that define fixture_chunks",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=None,
        help="Path to adversarial_cases.json (default: data/adversarial_cases.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Report JSON path (default: outputs/samples/adversarial_eval_report[_full].json)",
    )
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--max-context-tokens", type=int, default=1200)
    parser.add_argument("--skip-evidence-eval", action="store_true", default=True)
    parser.add_argument("--skip-critical-review", action="store_true", default=True)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check full corpus resources (live full)",
    )
    return parser.parse_args()


def _default_output(args: argparse.Namespace) -> Path:
    if args.output:
        return args.output
    suffix = "_full" if args.retrieval_mode == "full" else ""
    return STAGE10 / "outputs" / "samples" / f"adversarial_eval_report{suffix}.json"


def _mock_answers() -> dict[str, str]:
    refusal = "Based on the provided literature, this question cannot be answered."
    good = (
        "**Answer:** Metformin may benefit cardiovascular risk [1]. "
        "AMPK-related mechanisms are discussed [2].\n\n"
        "**Evidence Summary:**\n"
        "- Cardiovascular outcomes with metformin [1]\n"
        "- AMPK and fibrosis [2]\n"
    )
    tavr = (
        "**Answer:** TAVR (transcatheter aortic valve replacement) may improve "
        "functional status in selected elderly patients [1].\n\n"
        "**Evidence Summary:**\n"
        "- TAVR outcomes in seniors [1]\n"
    )
    safe_cite = (
        "**Answer:** Metformin has a known safety profile in adults [1].\n\n"
        "**Evidence Summary:**\n"
        "- Safety note [1]\n"
    )
    return {
        "ood_2025_fda": refusal,
        "induce_fabrication_side_effects": refusal,
        "terminology_tavr": tavr,
        "fake_citation_99": safe_cite,
        "normal_metformin": good,
    }


def _build_mock_pipeline():
    from bootstrap import bootstrap_paths

    bootstrap_paths(STAGE10)
    from config import Stage10Config
    from constrained_pipeline import ConstrainedGenerationPipeline
    from context_assembler import ContextAssembler

    answers = _mock_answers()

    class MockLLM:
        def __init__(self) -> None:
            self._case_id = "normal_metformin"

        def set_case(self, case_id: str) -> None:
            self._case_id = case_id

        def generate(self, prompt: str, **kwargs: Any) -> str:
            blob = (kwargs.get("system_prompt") or "") + prompt
            if "Draft:\n" not in blob and "CORRECTION REQUIRED" not in blob:
                return "Draft from evidence."
            return answers.get(self._case_id, answers["normal_metformin"])

    class NoRetrieval:
        def run(self, query: str) -> dict[str, Any]:
            return {"query": query, "retrieval": {"fused": []}, "reranked": []}

    llm = MockLLM()
    pipe = ConstrainedGenerationPipeline(
        retrieval_pipeline=NoRetrieval(),
        context_assembler=ContextAssembler(tokenizer_name=None),
        llm_generator=llm,
        config=Stage10Config(max_retries=1),
        skip_evidence_eval=True,
        skip_critical_review=True,
        run_optional_eval=True,
    )
    return pipe, llm


def _build_live_pipeline(args: argparse.Namespace):
    from bootstrap import bootstrap_paths
    from config import Stage10Config
    from constrained_pipeline import ConstrainedGenerationPipeline

    bootstrap_paths(STAGE10)
    cfg_kwargs: dict[str, Any] = {}
    if args.max_retries is not None:
        cfg_kwargs["max_retries"] = args.max_retries
    config = Stage10Config(**cfg_kwargs) if cfg_kwargs else None
    return ConstrainedGenerationPipeline.from_mode(
        args.retrieval_mode,
        config=config,
        skip_evidence_eval=args.skip_evidence_eval,
        skip_critical_review=args.skip_critical_review,
        max_context_tokens=args.max_context_tokens,
        run_optional_eval=True,
        llm_timeout=args.timeout,
    )


def main() -> int:
    args = _parse_args()

    from adversarial_eval import (
        AdversarialCase,
        default_cases_path,
        load_adversarial_cases,
        run_adversarial_eval,
        save_report,
    )
    from resources import check_full_corpus_resources

    if args.check_only:
        report = check_full_corpus_resources(STAGE10)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report.get("ready") else 1

    cases_path = args.cases or default_cases_path(STAGE10)
    cases = load_adversarial_cases(cases_path)
    if args.fixture_only:
        cases = [c for c in cases if c.use_fixture()]

    if args.mock:
        pipe, llm = _build_mock_pipeline()

        def run_case(case: AdversarialCase) -> dict[str, Any]:
            llm.set_case(case.id)
            chunks = case.fixture_chunks if case.fixture_chunks is not None else []
            return pipe.run(case.query, fixture_chunks=chunks)

    elif args.mode == "fixture":
        from bootstrap import bootstrap_paths

        bootstrap_paths(STAGE10)
        pipe = _build_live_pipeline(args)

        def run_case(case: AdversarialCase) -> dict[str, Any]:
            if case.use_fixture():
                return pipe.run(case.query, fixture_chunks=case.fixture_chunks)
            return pipe.run(case.query)

    else:  # live
        from bootstrap import bootstrap_paths

        bootstrap_paths(STAGE10)
        pipe = _build_live_pipeline(args)

        def run_case(case: AdversarialCase) -> dict[str, Any]:
            if case.use_fixture() and args.fixture_only:
                return pipe.run(case.query, fixture_chunks=case.fixture_chunks)
            return pipe.run(case.query)

    started = time.perf_counter()
    report = run_adversarial_eval(cases, run_case)
    report["run_meta"] = {
        "mode": "mock" if args.mock else args.mode,
        "retrieval_mode": args.retrieval_mode,
        "fixture_only": args.fixture_only,
        "cases_path": str(cases_path),
        "case_count": len(cases),
    }
    out_path = save_report(report, _default_output(args))
    elapsed = round(time.perf_counter() - started, 3)

    metrics = report["metrics"]
    print(f"Wrote report: {out_path}")
    print(f"Cases: {metrics['total_cases']} | elapsed: {elapsed}s")
    print(
        "hallucination_rate:",
        metrics.get("hallucination_rate"),
        f"({metrics.get('hallucination_failures')}/{metrics.get('hallucination_denominator')})",
    )
    print("refusal_hit_rate:", metrics.get("refusal_hit_rate"))
    print("citation_accuracy:", metrics.get("citation_accuracy"))
    print("format_compliance_rate:", metrics.get("format_compliance_rate"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
