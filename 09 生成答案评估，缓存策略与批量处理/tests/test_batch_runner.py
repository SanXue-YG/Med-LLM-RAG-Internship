from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from batch_runner import BatchRunner


def test_run_batch_preserves_input_order() -> None:
    runner = BatchRunner(max_workers=4)
    queries = ["q1", "q2", "q3", "q4"]

    def task_fn(q: str) -> dict[str, str]:
        if q == "q1":
            time.sleep(0.03)
        if q == "q2":
            time.sleep(0.01)
        return {"answer": f"ok-{q}"}

    results = runner.run_batch(queries, task_fn)
    assert [r["query"] for r in results] == queries
    assert all(r["status"] == "ok" for r in results)


def test_run_batch_isolates_failures() -> None:
    runner = BatchRunner(max_workers=3)
    queries = ["good-1", "bad", "good-2"]

    def task_fn(q: str) -> dict[str, str]:
        if q == "bad":
            raise ValueError("boom")
        return {"answer": q}

    results = runner.run_batch(queries, task_fn)
    by_query = {r["query"]: r for r in results}

    assert by_query["good-1"]["status"] == "ok"
    assert by_query["good-2"]["status"] == "ok"
    assert by_query["bad"]["status"] == "error"
    assert "boom" in by_query["bad"]["error"]


def test_summarize_reports_avg_latency_and_error_rate() -> None:
    runner = BatchRunner(max_workers=2)
    queries = ["ok", "bad"]

    def task_fn(q: str) -> dict[str, str]:
        if q == "bad":
            raise RuntimeError("x")
        return {"answer": "y"}

    results = runner.run_batch(queries, task_fn)
    stats = runner.summarize(results).to_dict()
    assert stats["total"] == 2
    assert stats["failed"] == 1
    assert stats["succeeded"] == 1
    assert 0.0 <= stats["error_rate"] <= 1.0

