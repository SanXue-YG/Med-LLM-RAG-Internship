"""SSE helpers for pseudo-streaming (chunk a finished answer).

This is **not** Ollama token-level streaming. Stage 11 MVP finishes the full
RAG/constraint pipeline first, then pushes ``token`` events for UX / API shape.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator

# Prefer sentence/clause breaks; fall back to fixed windows.
_SPLIT_RE = re.compile(r"(?<=[。！？.!?\n])")


def format_sse(event: str, data: Any) -> str:
    """Encode one SSE message (``event`` + JSON ``data`` + blank line)."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def chunk_answer_pseudo(text: str, *, window: int = 32) -> list[str]:
    """Split ``answer`` into pseudo-token chunks (sentence-ish, then window)."""
    if not text:
        return []
    if window < 1:
        window = 1

    parts: list[str] = []
    for piece in _SPLIT_RE.split(text):
        if not piece:
            continue
        if len(piece) <= window:
            parts.append(piece)
            continue
        for i in range(0, len(piece), window):
            parts.append(piece[i : i + window])
    return parts


def iter_pseudo_tokens(text: str, *, window: int = 32) -> Iterator[str]:
    yield from chunk_answer_pseudo(text, window=window)
