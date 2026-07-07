"""Batch execution utility for stage 09.

Concurrency rule:
- Parallel across multiple queries.
- Single-query internal stages remain sequential.
"""

from __future__ import annotations

import os
import importlib.util
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def _load_stage09_default_config() -> Any:
    """Always load local stage09 config to avoid cross-stage name collisions."""
    config_path = Path(__file__).with_name("config.py")
    spec = importlib.util.spec_from_file_location("stage09_local_config_batch", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load config from {config_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.DEFAULT_CONFIG


DEFAULT_CONFIG = _load_stage09_default_config()


@dataclass
class BatchStats:
    total: int
    succeeded: int
    failed: int
    avg_latency_seconds: float
    error_rate: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "avg_latency_seconds": round(self.avg_latency_seconds, 4),
            "error_rate": round(self.error_rate, 4),
        }


class BatchRunner:
    def __init__(self, *, max_workers: int | None = None) -> None:
        cpu_bound_default = min(4, os.cpu_count() or 1)
        config_default = max(1, DEFAULT_CONFIG.max_workers)
        self.max_workers = max_workers if max_workers is not None else min(config_default, cpu_bound_default)

    def run_batch(
        self,
        queries: list[str],
        task_fn: Callable[[str], dict[str, Any]],
        *,
        max_workers: int | None = None,
    ) -> list[dict[str, Any]]:
        workers = max_workers if max_workers is not None else self.max_workers
        if workers <= 1:
            return [self._run_single(i, q, task_fn) for i, q in enumerate(queries)]

        indexed = list(enumerate(queries))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda pair: self._run_single(pair[0], pair[1], task_fn), indexed))

        results.sort(key=lambda x: x["_index"])
        return results

    def summarize(self, results: list[dict[str, Any]]) -> BatchStats:
        total = len(results)
        failed = sum(1 for r in results if r.get("status") == "error")
        succeeded = total - failed
        avg_latency = sum(float(r.get("latency_seconds", 0.0)) for r in results) / total if total else 0.0
        error_rate = failed / total if total else 0.0
        return BatchStats(
            total=total,
            succeeded=succeeded,
            failed=failed,
            avg_latency_seconds=avg_latency,
            error_rate=error_rate,
        )

    @staticmethod
    def _run_single(index: int, query: str, task_fn: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            payload = task_fn(query) or {}
            latency = time.perf_counter() - start
            return {
                "_index": index,
                "query": query,
                "status": "ok",
                "latency_seconds": round(latency, 4),
                **payload,
            }
        except Exception as exc:  # noqa: BLE001
            latency = time.perf_counter() - start
            return {
                "_index": index,
                "query": query,
                "status": "error",
                "latency_seconds": round(latency, 4),
                "error": str(exc),
            }

