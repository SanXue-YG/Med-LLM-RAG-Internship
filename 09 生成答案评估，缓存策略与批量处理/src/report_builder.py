"""Build stage 09 eval/cache/batch summary reports."""

from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any


def _safe_mean(values: list[float]) -> float:
    return round(mean(values), 4) if values else 0.0


def summarize_evaluation_distribution(results: list[dict[str, Any]]) -> dict[str, float]:
    rouge1: list[float] = []
    key_recall: list[float] = []
    hallucination: list[float] = []

    for item in results:
        if item.get("status") == "error":
            continue
        evaluation = item.get("evaluation") or {}
        rouge = evaluation.get("rouge") or {}
        rouge1.append(float(rouge.get("rouge1", 0.0)))
        key_recall.append(float(evaluation.get("key_info_recall", 0.0)))
        hallucination.append(float(evaluation.get("hallucination_risk", 0.0)))

    return {
        "rouge1_avg": _safe_mean(rouge1),
        "key_info_recall_avg": _safe_mean(key_recall),
        "hallucination_risk_avg": _safe_mean(hallucination),
        "sample_count": float(len(rouge1)),
    }


def summarize_cache_metrics(results: list[dict[str, Any]]) -> dict[str, float | int]:
    hits = sum(1 for item in results if (item.get("cache") or {}).get("hit") is True)
    total = len(results)
    return {
        "hits": hits,
        "misses": total - hits,
        "hit_rate": round(hits / total, 4) if total else 0.0,
    }


def collect_failures(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for item in results:
        if item.get("status") == "error":
            failures.append({"query": str(item.get("query", "")), "reason": str(item.get("error", "unknown"))})
            continue
        answer = str((item.get("generation") or {}).get("answer", "") or "")
        if not answer.strip():
            failures.append({"query": str(item.get("query", "")), "reason": "empty answer"})
    return failures


def build_eval_cache_batch_report(
    *,
    mode: str,
    config: dict[str, Any],
    first_pass: list[dict[str, Any]],
    second_pass: list[dict[str, Any]] | None = None,
    batch_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    second_pass = second_pass or []
    first_eval = summarize_evaluation_distribution(first_pass)
    second_eval = summarize_evaluation_distribution(second_pass) if second_pass else {}

    first_cache = summarize_cache_metrics(first_pass)
    second_cache = summarize_cache_metrics(second_pass) if second_pass else {}

    first_failures = collect_failures(first_pass)
    second_failures = collect_failures(second_pass) if second_pass else []

    latencies = [float(item.get("latency_seconds", 0.0)) for item in first_pass if "latency_seconds" in item]
    if batch_stats and "avg_latency_seconds" in batch_stats:
        avg_latency = float(batch_stats["avg_latency_seconds"])
    else:
        avg_latency = _safe_mean(latencies)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "query_count": len(first_pass),
        "config": config,
        "summary": {
            "cache_first_pass": first_cache,
            "cache_second_pass": second_cache,
            "avg_latency_seconds": avg_latency,
            "evaluation_first_pass": first_eval,
            "evaluation_second_pass": second_eval,
            "failures_first_pass": first_failures,
            "failures_second_pass": second_failures,
        },
        "batch_stats": batch_stats or {},
        "first_pass": first_pass,
        "second_pass": second_pass,
        "extensions": {},
    }
