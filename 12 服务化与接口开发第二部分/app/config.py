"""Stage 12 runtime configuration (compatible with stage-11 env names)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

STAGE12_DIR = Path(__file__).resolve().parent.parent

# Load local .env if present (does not override already-set process env).
load_dotenv(STAGE12_DIR / ".env", override=False)

RetrievalMode = Literal["sample", "full"]
PipelineBackend = Literal["constrained10", "medical08"]


def _env(*names: str, default: str = "") -> str:
    for name in names:
        raw = os.getenv(name)
        if raw is not None and raw.strip():
            return raw.strip()
    return default


@dataclass(frozen=True)
class Stage12Config:
    """Process-level settings; aliases STAGE12_* → STAGE11_* / MED_RAG_*."""

    host: str = field(
        default_factory=lambda: _env("STAGE12_HOST", "STAGE11_HOST", default="127.0.0.1")
    )
    port: int = field(
        default_factory=lambda: int(_env("STAGE12_PORT", "STAGE11_PORT", default="8000"))
    )

    retrieval_mode: RetrievalMode = field(
        default_factory=lambda: _env(  # type: ignore[arg-type]
            "MED_RAG_RETRIEVAL_MODE",
            "STAGE12_RETRIEVAL_MODE",
            "STAGE11_RETRIEVAL_MODE",
            default="sample",
        )
    )

    pipeline_backend: PipelineBackend = field(
        default_factory=lambda: _env(  # type: ignore[arg-type]
            "STAGE12_PIPELINE_BACKEND",
            "STAGE11_PIPELINE_BACKEND",
            default="constrained10",
        )
    )

    # Prefer stage-12 log dir so qa_calls stay with ops work; override via env.
    log_dir: Path = field(
        default_factory=lambda: Path(
            _env(
                "STAGE12_LOG_DIR",
                "STAGE11_LOG_DIR",
                default=str(STAGE12_DIR / "outputs" / "logs"),
            )
        )
    )

    ollama_base_url: str = field(
        default_factory=lambda: _env("OLLAMA_BASE_URL", default="http://127.0.0.1:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: _env("OLLAMA_MODEL", default="deepseek-r1:7b")
    )

    session_ttl_seconds: int = field(
        default_factory=lambda: int(
            _env("STAGE12_SESSION_TTL", "STAGE11_SESSION_TTL", default="3600")
        )
    )
    session_max_turns: int = field(
        default_factory=lambda: int(
            _env("STAGE12_SESSION_MAX_TURNS", "STAGE11_SESSION_MAX_TURNS", default="10")
        )
    )

    documents_mode: RetrievalMode = field(
        default_factory=lambda: _env(  # type: ignore[arg-type]
            "STAGE12_DOCUMENTS_MODE",
            "MED_RAG_RETRIEVAL_MODE",
            default="sample",
        )
    )


DEFAULT_CONFIG = Stage12Config()
