"""Shared process state (pipeline readiness etc.)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppRuntimeState:
    """Mutable runtime flags; stage 2+ sets ``pipeline_loaded`` after lazy init."""

    pipeline_loaded: bool = False
    pipeline_mode: str | None = None
    pipeline_backend: str | None = None
    last_error: str | None = None


RUNTIME = AppRuntimeState()
