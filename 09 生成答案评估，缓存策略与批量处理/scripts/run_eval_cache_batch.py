"""Stage 5: batch eval + cache + report export CLI.

Outputs:
- outputs/samples/eval_cache_batch_report.json (latest snapshot)
- outputs/logs/eval_cache_batch_YYYYmmdd_HHMMSS.json (history log)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_QUERIES = [
    "What is the treatment for MI?",
    "metformin cardiovascular effects",
    "papers on malaria after 2015",
    "warfarin atrial fibrillation elderly",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stage09 eval/cache/batch report.")
    parser.add_argument(
        "--mode",
        choices=("offline", "mock", "live"),
        default="offline",
        help="offline=08 generation_eval snapshots; mock=fake adapter; live=Ollama pipeline",
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
    parser.add_argument("--timeout", type=float, default=180.0, help="Live mode only")
    return parser.parse_args()


def _load_ground_truth(stage09: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads((stage09 / "data" / "ground_truth.json").read_text(encoding="utf-8"))
    return {item["query"]: item for item in payload.get("queries", [])}


def _context_for_query(query: str) -> str:
    return f"ctx::{query}"


def _build_pipeline(args: argparse.Namespace, paths: dict[str, Path]) -> tuple[Any, str, str]:
    from answer_evaluator import AnswerEvaluator
    from generation_cache import GenerationCache
    from model_adapter import GenerationRequest, GenerationResponse, PipelineModelAdapter, SnapshotModelAdapter
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
        return pipe, "mock", "mock-model"

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
        return pipe, "offline", model_name

    # live mode
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
    return pipe, "live", OLLAMA_MODEL


def _run_pass(
    pipe: Any,
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

    runner = BatchRunner(max_workers=max_workers)
    results = runner.run_batch(queries, task_fn, max_workers=max_workers)
    stats = runner.summarize(results).to_dict()
    return results, stats


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

    from report_builder import build_eval_cache_batch_report

    gt_by_query = _load_ground_truth(stage09)
    pipe, mode, model_name = _build_pipeline(args, paths)

    use_cache = not args.no_cache
    first_pass, first_batch_stats = _run_pass(
        pipe,
        list(args.queries),
        gt_by_query,
        use_cache=use_cache,
        force_refresh=False,
        temperature=args.temperature,
        max_workers=args.max_workers,
        model_name=model_name,
    )

    second_pass: list[dict[str, Any]] = []
    second_batch_stats: dict[str, Any] | None = None
    if use_cache and not args.skip_second_pass:
        second_pass, second_batch_stats = _run_pass(
            pipe,
            list(args.queries),
            gt_by_query,
            use_cache=True,
            force_refresh=False,
            temperature=args.temperature,
            max_workers=args.max_workers,
            model_name=model_name,
        )

    report = build_eval_cache_batch_report(
        mode=mode,
        config={
            "queries": list(args.queries),
            "temperature": args.temperature,
            "use_cache": use_cache,
            "max_workers": args.max_workers,
            "model_name": model_name,
        },
        first_pass=first_pass,
        second_pass=second_pass,
        batch_stats=second_batch_stats or first_batch_stats,
    )

    out_samples = stage09 / "outputs" / "samples" / "eval_cache_batch_report.json"
    out_logs_dir = stage09 / "outputs" / "logs"
    out_logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_log = out_logs_dir / f"eval_cache_batch_{stamp}.json"

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    out_samples.write_text(payload, encoding="utf-8")
    out_log.write_text(payload, encoding="utf-8")

    summary = report["summary"]
    print(f"[OK] mode={mode} queries={len(first_pass)}")
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
