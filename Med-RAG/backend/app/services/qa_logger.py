"""Append-only QA call logger (JSONL), with query truncation for privacy."""

from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock
from typing import Any

from app.config import DEFAULT_CONFIG, Stage11Config
from app.core.logging import get_logger

logger = get_logger("qa_logger")


class QACallLogger:
    """Write one JSON object per line to ``outputs/logs/qa_calls.jsonl``."""

    def __init__(self, config: Stage11Config | None = None, *, query_preview_chars: int = 80) -> None:
        self.config = config or DEFAULT_CONFIG
        self.query_preview_chars = query_preview_chars
        self._lock = Lock()
        self.path = Path(self.config.log_dir) / "qa_calls.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        *,
        request_id: str,
        query: str,
        status: str,
        latency_ms: float,
        session_id: str | None = None,
        code: int = 0,
        top_k: int | None = None,
        n_sources: int | None = None,
        error_detail: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        preview = (query or "").replace("\n", " ").strip()
        if len(preview) > self.query_preview_chars:
            preview = preview[: self.query_preview_chars] + "…"

        record: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": request_id,
            "session_id": session_id,
            "status": status,  # ok | error
            "code": code,
            "latency_ms": round(float(latency_ms), 1),
            "query_preview": preview,
            "query_chars": len(query or ""),
            "top_k": top_k,
            "n_sources": n_sources,
        }
        if error_detail is not None:
            record["error_detail"] = error_detail
        if extra:
            record.update(extra)

        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            try:
                # Avoid mkdir from odd worker threads on some Windows/cloud-synced paths.
                if not self.path.parent.is_dir():
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError as exc:
                logger.warning(
                    "qa_log_write_failed path=%s err=%s record=%s",
                    self.path,
                    exc,
                    line[:300],
                )
        logger.info(
            "qa_call status=%s code=%s request_id=%s latency_ms=%.1f",
            status,
            code,
            request_id,
            latency_ms,
        )
