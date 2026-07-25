"""Stage 11 runtime configuration.

Defaults favor fast API-contract development (sample retrieval).
Full-corpus smoke is opt-in via env / config change + process restart.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

RetrievalMode = Literal["sample", "full"]
PipelineBackend = Literal["constrained10", "medical08"]

STAGE11_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


@dataclass(frozen=True)
class Stage11Config:
    """Process-level API / pipeline settings (not per-request)."""

    host: str = field(default_factory=lambda: _env("STAGE11_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("STAGE11_PORT", "8000")))

    # Default sample — avoid cold-starting 6.1M index while building the HTTP shell.
    retrieval_mode: RetrievalMode = field(
        default_factory=lambda: _env(  # type: ignore[arg-type]
            "MED_RAG_RETRIEVAL_MODE",
            _env("STAGE11_RETRIEVAL_MODE", "sample"),
        )
    )

    pipeline_backend: PipelineBackend = field(
        default_factory=lambda: _env(  # type: ignore[arg-type]
            "STAGE11_PIPELINE_BACKEND", "constrained10"
        )
    )

    log_dir: Path = field(
        default_factory=lambda: Path(
            _env("STAGE11_LOG_DIR", str(STAGE11_DIR / "outputs" / "logs"))
        )
    )

    ollama_base_url: str = field(
        default_factory=lambda: _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: _env("OLLAMA_MODEL", "deepseek-r1:7b")
    )

    # Session / QA knobs (used from stage 2+)
    session_ttl_seconds: int = field(
        default_factory=lambda: int(_env("STAGE11_SESSION_TTL", "3600"))
    )
    session_max_turns: int = field(
        default_factory=lambda: int(_env("STAGE11_SESSION_MAX_TURNS", "10"))
    )
    query_max_length: int = 2000
    top_k_default: int = 5
    top_k_min: int = 1
    top_k_max: int = 20

    # Pseudo-SSE: answer is chunked after full pipeline.run (not live tokens).
    stream_chunk_chars: int = field(
        default_factory=lambda: int(_env("STAGE11_STREAM_CHUNK_CHARS", "32"))
    )


DEFAULT_CONFIG = Stage11Config()
