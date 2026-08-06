"""Stage 10 runtime configuration.

Fixed defaults for full-corpus-first validation and constraint retries.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

RetrievalMode = Literal["sample", "full"]
RefStrictness = Literal["relaxed", "strict"]


@dataclass(frozen=True)
class Stage10Config:
    """Active defaults for stage 10 (full-first)."""

    # Corpus / retrieval — default production full index (09 stage 7 paths)
    retrieval_mode: RetrievalMode = os.getenv("STAGE10_RETRIEVAL_MODE", "full")  # type: ignore[assignment]

    # Constraint retry loop (LLM re-generate after CitationGuard/FormatChecker fail)
    max_retries: int = int(os.getenv("STAGE10_MAX_RETRIES", "1"))  # dev default; eval may use 2
    temperature: float = float(os.getenv("STAGE10_TEMPERATURE", "0.2"))

    # FormatChecker
    ref_strictness: RefStrictness = os.getenv("STAGE10_REF_STRICTNESS", "relaxed")  # type: ignore[assignment]

    # Concurrent live queries (Ollama-bound; keep low on full corpus)
    max_workers: int = int(os.getenv("STAGE10_MAX_WORKERS", "2"))

    # Fixed refusal sentences (EN canonical; ZH alias)
    refusal_en: str = (
        "Based on the provided literature, this question cannot be answered."
    )
    refusal_zh: str = "根据现有文献无法回答此问题"

    # Placeholders for later stages (not read by pipeline yet)
    citation_missing_policy: str = os.getenv(
        "STAGE10_CITATION_MISSING_POLICY", "warn"
    )  # warn | fail


DEFAULT_CONFIG = Stage10Config()
