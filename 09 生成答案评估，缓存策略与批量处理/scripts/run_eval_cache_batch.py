"""Stage 5/7: batch eval + cache + report export CLI.

Outputs (default):
- sample/offline: outputs/samples/eval_cache_batch_report.json
- live + --retrieval-mode full: outputs/samples/eval_cache_batch_report_full.json
- logs: outputs/logs/eval_cache_batch[_full]_YYYYmmdd_HHMMSS.json

Examples:
    python scripts/run_eval_cache_batch.py --mode offline
    python scripts/run_eval_cache_batch.py --mode live
    python scripts/run_eval_cache_batch.py --mode live --retrieval-mode full --max-workers 2
    python scripts/run_eval_cache_batch.py --mode live --retrieval-mode full --check-only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

DEFAULT_QUERIES = [
    "What is the treatment for MI?",
    "metformin cardiovascular effects",
    "papers on malaria after 2015",
    "warfarin atrial fibrillation elderly",
]


@dataclass
class Runtime:
    pipe_eval: Any
    generation_pipeline: Any | None
    mode: str
    model_name: str
    retrieval_mode: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stage09 eval/cache/batch report.")
    parser.add_argument(
        "--mode",
        choices=("offline", "mock", "live"),
        default="offline",
        help="offline=08 generation_eval snapshots; mock=fake adapter; live=Ollama pipeline",
    )
    parser.add_argument(
        "--retrieval-mode",
        choices=("sample", "full"),
        default="sample",
        help="live only: sample=06 pipeline_eval.json offline reranked; full=610万 RetrievalPipeline",
    )
    parser.add_argument("--queries", nargs="*", default=DEFAULT_QUERIES, help="Queries to evaluate")
    parser.add_argument("--max-workers", type=int, default=None, help="BatchRunner workers")
    parser.add_argument("--temperature", type=float, default=0.2, help="Generation/cache temperature")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache lookup/write")
    parser.add_argument(
        "--skip-second-pass",
        action="store_true",
        help="Skip second pass (cache warm-up demo)",
    )
    parser.add_argument("--max-context-tokens", type=int, default=1200, help="Live mode only")
    parser.add_argument("--skip-evidence-eval", action="store_true", help="Live mode only")
    parser.add_argument("--skip-critical-review", action="store_true", help="Live mode only")
    parser.add_argument("--skip-rerank", action="store_true", help="Live full mode: skip reranker")
    parser.add_argument("--timeout", type=float, default=180.0, help="Live mode only")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Report JSON path (default: sample or full report filename)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="With --mode live --retrieval-mode full: only check full corpus resources",
    )
    args = parser.parse_args()
    if args.retrieval_mode == "full" and args.mode != "live":
        parser.error("--retrieval-mode full requires --mode live")
    return args


def _load_ground_truth(stage09: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads((stage09 / "data" / "ground_truth.json").read_text(encoding="utf-8"))
    return {item["query"]: item for item in payload.get("queries", [])}


def _context_for_query(query: str) -> str:
    return f"ctx::{query}"


def _build_runtime(args: argparse.Namespace, paths: dict[str, Path]) -> Runtime:
    from answer_evaluator import AnswerEvaluator
    from generation_cache import GenerationCache
    from model_adapter import GenerationRequest, GenerationResponse, SnapshotModelAdapter
    from pipeline_with_eval import PipelineWithEval

    evaluator = AnswerEvaluator()
    cache = GenerationCache()

    if args.mode == "mock":

        class _MockAdapter:
            def generate(self, request: GenerationRequest) -> GenerationResponse:
                answer = f"Mock answer for: {request.query}"
                raw = {"answer": answer, "sources": [{"doc_id": "MOCK"}]}
                return GenerationResponse(
                    answer=answer,
                    sources=raw["sources"],
                    model_name="mock-model",
                    provider="mock",
                    raw=raw,
                )

        pipe = PipelineWithEval(
            model_adapter=_MockAdapter(),
            evaluator=evaluator,
            cache=cache,
            provider="mock",
            default_model_name="mock-model",
        )
        return Runtime(pipe, None, "mock", "mock-model", "sample")

    if args.mode == "offline":
        snapshot_path = paths["stage08"] / "outputs" / "samples" / "generation_eval.json"
        snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshots = {item["query"]: item for item in snapshot_payload.get("queries", [])}
        model_name = str(snapshot_payload.get("config", {}).get("model", "snapshot-model"))
        adapter = SnapshotModelAdapter(
            snapshots,
            provider="stage08_snapshot",
            model_name=model_name,
        )
        pipe = PipelineWithEval(
            model_adapter=adapter,
            evaluator=evaluator,
            cache=cache,
            provider="stage08_snapshot",
            default_model_name=model_name,
        )
        return Runtime(pipe, None, "offline", model_name, "sample")

    if args.retrieval_mode == "full":
        from full_eval import build_pipeline_with_eval_live_full

        pipe_eval, generation_pipe, model_name = build_pipeline_with_eval_live_full(
            paths["stage06"],
            paths["stage07"],
            paths["stage08"],
            skip_evidence_eval=args.skip_evidence_eval,
            skip_critical_review=args.skip_critical_review,
            max_context_tokens=args.max_context_tokens,
            timeout=args.timeout,
            skip_rerank=args.skip_rerank,
        )
        return Runtime(pipe_eval, generation_pipe, "live", model_name, "full")

    sys.path.insert(0, str(paths["stage08"] / "src"))
    sys.path.insert(0, str(paths["stage07"] / "src"))

    from bootstrap import OLLAMA_BASE_URL, OLLAMA_MODEL
    from context_assembler import ContextAssembler
    from generation_pipeline import MedicalGenerationPipeline
    from llm_generator import LLMGenerator

    eval_file = paths["stage06"] / "outputs" / "samples" / "pipeline_eval.json"
    eval_payload = json.loads(eval_file.read_text(encoding="utf-8"))
    per_query = {item["query"]: item for item in eval_payload.get("queries", [])}
    fallback = eval_payload.get("queries", [{}])[0]

    class OfflineRetrievalAdapter:
        def __init__(self) -> None:
            self.payload_by_query = per_query
            self.fallback = fallback

        def run(self, query: str) -> dict[str, Any]:
            payload = self.payload_by_query.get(query) or self.fallback
            return {
                "query": query,
                "retrieval": payload.get("retrieval", {"fused": []}),
                "reranked": payload.get("reranked", []),
            }

    retrieval = OfflineRetrievalAdapter()
    assembler = ContextAssembler(tokenizer_name=None)
    llm = LLMGenerator(model_name=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, timeout=args.timeout)
    generation_pipe = MedicalGenerationPipeline(
        retrieval_pipeline=retrieval,
        context_assembler=assembler,
        llm_generator=llm,
        skip_evidence_eval=args.skip_evidence_eval,
        skip_critical_review=args.skip_critical_review,
        max_context_tokens=args.max_context_tokens,
    )
    pipe = PipelineWithEval.from_pipeline(
        generation_pipe,
        evaluator=evaluator,
        cache=cache,
        provider="stage08_live",
        model_name=OLLAMA_MODEL,
    )
    return Runtime(pipe, None, "live", OLLAMA_MODEL, "sample")


def _make_task_fn(
    runtime: Runtime,
    gt_by_query: dict[str, dict[str, Any]],
    *,
    use_cache: bool,
    force_refresh: bool,
    temperature: float,
    model_name: str,
) -> Callable[[str], dict[str, Any]]:
    if runtime.mode == "live" and runtime.retrieval_mode == "full":
        from full_eval import run_live_full_eval_task

        def task_fn(query: str) -> dict[str, Any]:
            gt = gt_by_query.get(query)
            if gt is None:
                raise KeyError(f"ground truth missing for query: {query}")
            return run_live_full_eval_task(
                runtime.pipe_eval,
                runtime.generation_pipeline,
                query,
                gt,
                use_cache=use_cache,
                force_refresh=force_refresh,
                temperature=temperature,
                model_name=model_name,
            )

        return task_fn

    pipe = runtime.pipe_eval

    def task_fn(query: str) -> dict[str, Any]:
        gt = gt_by_query.get(query)
        if gt is None:
            raise KeyError(f"ground truth missing for query: {query}")
        started = time.perf_counter()
        result = pipe.run_with_cache_and_eval(
            query,
            ground_truth_entry=gt,
            use_cache=use_cache,
            force_refresh=force_refresh,
            context_text=_context_for_query(query),
            model_name=model_name,
            temperature=temperature,
        )
        result["latency_seconds"] = round(time.perf_counter() - started, 4)
        result["status"] = "ok"
        return result

    return task_fn


def _run_pass(
    runtime: Runtime,
    queries: list[str],
    gt_by_query: dict[str, dict[str, Any]],
    *,
    use_cache: bool,
    force_refresh: bool,
    temperature: float,
    max_workers: int | None,
    model_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    from batch_runner import BatchRunner

    task_fn = _make_task_fn(
        runtime,
        gt_by_query,
        use_cache=use_cache,
        force_refresh=force_refresh,
        temperature=temperature,
        model_name=model_name,
    )
    runner = BatchRunner(max_workers=max_workers)
    results = runner.run_batch(queries, task_fn, max_workers=max_workers)
    stats = runner.summarize(results).to_dict()
    return results, stats


def _resolve_output_paths(stage09: Path, args: argparse.Namespace) -> tuple[Path, str]:
    is_full = args.mode == "live" and args.retrieval_mode == "full"
    if args.output is not None:
        out_samples = args.output
    elif is_full:
        out_samples = stage09 / "outputs" / "samples" / "eval_cache_batch_report_full.json"
    else:
        out_samples = stage09 / "outputs" / "samples" / "eval_cache_batch_report.json"
    log_prefix = "eval_cache_batch_full" if is_full else "eval_cache_batch"
    return out_samples, log_prefix


def main() -> None:
    args = _parse_args()

    script_path = Path(__file__).resolve()
    stage09 = script_path.parents[1]
    root = stage09.parent
    paths = {
        "root": root,
        "stage06": root / "06 检索系统开发第二部分",
        "stage07": root / "07 生成模块与提示词工程第一部分",
        "stage08": root / "08 生成模块与提示词工程第二部分",
        "stage09": stage09,
    }

    sys.path.insert(0, str(stage09 / "src"))

    if args.check_only:
        if args.mode != "live" or args.retrieval_mode != "full":
            raise SystemExit("--check-only requires --mode live --retrieval-mode full")
        from full_eval import check_full_corpus_resources

        info = check_full_corpus_resources(paths["stage06"])
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return

    if args.mode == "live" and args.retrieval_mode == "full":
        from full_eval import check_full_corpus_resources

        resource_check = check_full_corpus_resources(paths["stage06"])
        if not resource_check.get("ready"):
            raise SystemExit(
                f"Full corpus resources not ready: {json.dumps(resource_check, ensure_ascii=False)}"
            )

    gt_by_query = _load_ground_truth(stage09)
    runtime = _build_runtime(args, paths)

    use_cache = not args.no_cache
    first_pass, first_batch_stats = _run_pass(
        runtime,
        list(args.queries),
        gt_by_query,
        use_cache=use_cache,
        force_refresh=False,
        temperature=args.temperature,
        max_workers=args.max_workers,
        model_name=runtime.model_name,
    )

    second_pass: list[dict[str, Any]] = []
    second_batch_stats: dict[str, Any] | None = None
    if use_cache and not args.skip_second_pass:
        second_pass, second_batch_stats = _run_pass(
            runtime,
            list(args.queries),
            gt_by_query,
            use_cache=True,
            force_refresh=False,
            temperature=args.temperature,
            max_workers=args.max_workers,
            model_name=runtime.model_name,
        )

    config = {
        "queries": list(args.queries),
        "temperature": args.temperature,
        "use_cache": use_cache,
        "max_workers": args.max_workers,
        "model_name": runtime.model_name,
        "retrieval_mode": runtime.retrieval_mode,
        "skip_evidence_eval": args.skip_evidence_eval,
        "skip_critical_review": args.skip_critical_review,
        "skip_rerank": args.skip_rerank,
    }

    if runtime.mode == "live" and runtime.retrieval_mode == "full":
        from full_eval import build_full_eval_report

        report = build_full_eval_report(
            mode="live",
            config=config,
            first_pass=first_pass,
            second_pass=second_pass,
            batch_stats=second_batch_stats or first_batch_stats,
            retrieval_mode="full",
            eval_subset="full_corpus",
        )
        report["extensions"]["cli"] = "run_eval_cache_batch.py --mode live --retrieval-mode full"
    else:
        from report_builder import build_eval_cache_batch_report

        report = build_eval_cache_batch_report(
            mode=runtime.mode,
            config=config,
            first_pass=first_pass,
            second_pass=second_pass,
            batch_stats=second_batch_stats or first_batch_stats,
        )

    out_samples, log_prefix = _resolve_output_paths(stage09, args)
    out_logs_dir = stage09 / "outputs" / "logs"
    out_logs_dir.mkdir(parents=True, exist_ok=True)
    out_samples.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_log = out_logs_dir / f"{log_prefix}_{stamp}.json"

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    out_samples.write_text(payload, encoding="utf-8")
    out_log.write_text(payload, encoding="utf-8")

    summary = report["summary"]
    print(
        f"[OK] mode={runtime.mode} retrieval_mode={runtime.retrieval_mode} "
        f"queries={len(first_pass)}"
    )
    print(
        f"cache first_pass hit_rate={summary['cache_first_pass']['hit_rate']} | "
        f"second_pass hit_rate={summary['cache_second_pass'].get('hit_rate', 0.0)}"
    )
    print(
        f"eval rouge1_avg={summary['evaluation_first_pass']['rouge1_avg']} | "
        f"key_info_recall_avg={summary['evaluation_first_pass']['key_info_recall_avg']}"
    )
    print(f"Saved sample: {out_samples}")
    print(f"Saved log:    {out_log}")


if __name__ == "__main__":
    main()
