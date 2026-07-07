"""Stage 09 runtime configuration.

This module centralizes fixed-path defaults and extension placeholders.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Stage09Config:
    # Stage-0 fixed defaults (active)
    ttl_seconds: int = int(os.getenv("STAGE09_TTL_SECONDS", "86400"))  # 24h
    max_entries: int = int(os.getenv("STAGE09_MAX_ENTRIES", "128"))
    max_temperature: float = float(os.getenv("STAGE09_MAX_TEMPERATURE", "0.3"))
    max_workers: int = int(os.getenv("STAGE09_MAX_WORKERS", "4"))

    # Stage-0 placeholders (not active yet)
    cache_backend: str = os.getenv("STAGE09_CACHE_BACKEND", "memory")
    ttl_policy: str = os.getenv("STAGE09_TTL_POLICY", "fixed")
    hallucination_weight_profile: str = os.getenv(
        "STAGE09_HALLUCINATION_WEIGHT_PROFILE", "default"
    )


DEFAULT_CONFIG = Stage09Config()

