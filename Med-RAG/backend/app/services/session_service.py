"""Thin session helpers — store remains stage-11 ``MemorySessionStore`` singleton."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def epoch_to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def record_to_detail(rec: Any) -> dict[str, Any]:
    """Map ``SessionRecord`` → SessionDetail-shaped dict (ISO timestamps)."""
    turns = [
        {
            "query": t.query,
            "answer": t.answer,
            "created_at": epoch_to_iso(float(t.created_at)),
            "meta": t.meta or None,
        }
        for t in rec.turns
    ]
    if hasattr(rec, "display_title"):
        title = rec.display_title()
    else:
        title = getattr(rec, "title", None) or None
        if not title and rec.turns:
            q = (rec.turns[0].query or "").strip().replace("\n", " ")
            title = (q[:48] + "…") if len(q) > 48 else (q or "New chat")
    return {
        "session_id": rec.session_id,
        "created_at": epoch_to_iso(float(rec.created_at)),
        "updated_at": epoch_to_iso(float(rec.updated_at)),
        "turn_count": len(rec.turns),
        "title": title or "New chat",
        "turns": turns,
    }
