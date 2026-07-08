from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from report_builder import build_eval_cache_batch_report, summarize_cache_metrics


def test_build_report_contains_summary_sections() -> None:
    first = [
        {
            "query": "q1",
            "status": "ok",
            "latency_seconds": 0.5,
            "cache": {"hit": False},
            "evaluation": {
                "rouge": {"rouge1": 0.4},
                "key_info_recall": 0.5,
                "hallucination_risk": 0.1,
            },
            "generation": {"answer": "ok"},
        }
    ]
    second = [
        {
            "query": "q1",
            "status": "ok",
            "latency_seconds": 0.01,
            "cache": {"hit": True},
            "evaluation": {
                "rouge": {"rouge1": 0.4},
                "key_info_recall": 0.5,
                "hallucination_risk": 0.1,
            },
            "generation": {"answer": "ok"},
        }
    ]
    report = build_eval_cache_batch_report(
        mode="mock",
        config={"temperature": 0.2},
        first_pass=first,
        second_pass=second,
        batch_stats={"avg_latency_seconds": 0.25},
    )
    assert report["summary"]["cache_second_pass"]["hit_rate"] == 1.0
    assert report["summary"]["evaluation_first_pass"]["rouge1_avg"] == 0.4


def test_summarize_cache_metrics() -> None:
    results = [{"cache": {"hit": True}}, {"cache": {"hit": False}}]
    stats = summarize_cache_metrics(results)
    assert stats["hits"] == 1
    assert stats["hit_rate"] == 0.5
