"""Stage 6 acceptance checks for baseline queries."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from answer_evaluator import AnswerEvaluator
from batch_runner import BatchRunner
from generation_cache import GenerationCache
from model_adapter import SnapshotModelAdapter
from pipeline_with_eval import PipelineWithEval

DEFAULT_QUERIES = [
    "What is the treatment for MI?",
    "metformin cardiovascular effects",
    "papers on malaria after 2015",
    "warfarin atrial fibrillation elderly",
]


def _load_gt() -> dict[str, dict]:
    payload = json.loads((ROOT / "data" / "ground_truth.json").read_text(encoding="utf-8"))
    return {item["query"]: item for item in payload["queries"]}


def _load_snapshots() -> dict[str, dict]:
    snapshot_path = ROOT.parent / "08 生成模块与提示词工程第二部分" / "outputs" / "samples" / "generation_eval.json"
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return {item["query"]: item for item in payload["queries"]}


def _build_pipe() -> PipelineWithEval:
    snapshots = _load_snapshots()
    return PipelineWithEval(
        model_adapter=SnapshotModelAdapter(snapshots, provider="stage08_snapshot", model_name="snapshot"),
        evaluator=AnswerEvaluator(),
        cache=GenerationCache(ttl_seconds=600),
        provider="stage08_snapshot",
        default_model_name="snapshot",
    )


def test_stage06_baseline_queries_have_evaluation_metrics() -> None:
    pipe = _build_pipe()
    gt = _load_gt()
    for query in DEFAULT_QUERIES:
        result = pipe.run_with_cache_and_eval(
            query,
            ground_truth_entry=gt[query],
            context_text=f"ctx::{query}",
            temperature=0.2,
            model_name="snapshot",
        )
        evaluation = result["evaluation"]
        assert evaluation["rouge"]["rouge1"] >= 0.0
        assert "key_info_recall" in evaluation
        assert "hallucination_risk" in evaluation
        assert "readability" in evaluation


def test_stage06_second_pass_cache_hit_for_all_queries() -> None:
    pipe = _build_pipe()
    gt = _load_gt()

    def task(query: str) -> dict:
        return pipe.run_with_cache_and_eval(
            query,
            ground_truth_entry=gt[query],
            context_text=f"ctx::{query}",
            temperature=0.2,
            model_name="snapshot",
        )

    runner = BatchRunner(max_workers=2)
    _ = runner.run_batch(DEFAULT_QUERIES, task)
    second = runner.run_batch(DEFAULT_QUERIES, task)
    assert len(second) == 4
    assert all(item["cache"]["hit"] is True for item in second)


def test_stage06_batch_returns_four_in_order() -> None:
    pipe = _build_pipe()
    gt = _load_gt()

    def task(query: str) -> dict:
        return pipe.run_with_cache_and_eval(
            query,
            ground_truth_entry=gt[query],
            context_text=f"ctx::{query}",
            temperature=0.2,
            model_name="snapshot",
        )

    runner = BatchRunner(max_workers=3)
    results = runner.run_batch(DEFAULT_QUERIES, task)
    assert [item["query"] for item in results] == DEFAULT_QUERIES
    assert all(item.get("status", "ok") == "ok" for item in results)
