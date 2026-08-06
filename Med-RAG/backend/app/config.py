"""Med-RAG runtime configuration (unified 11+12)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

RetrievalMode = Literal["sample", "full"]
PipelineBackend = Literal["constrained10", "medical08"]

BACKEND_DIR = Path(__file__).resolve().parent.parent
MED_RAG_HOME = BACKEND_DIR.parent

# Load Med-RAG/.env (process env wins)
load_dotenv(MED_RAG_HOME / ".env", override=False)


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        val = os.getenv(name)
        if val is not None and str(val).strip():
            return str(val).strip()
    return default


@dataclass(frozen=True)
class MedRagConfig:
    """Process-level API / pipeline settings (not per-request)."""

    host: str = field(
        default_factory=lambda: _env_first("MED_RAG_HOST", "STAGE12_HOST", "STAGE11_HOST", default="127.0.0.1")
    )
    port: int = field(
        default_factory=lambda: int(
            _env_first("MED_RAG_PORT", "STAGE12_PORT", "STAGE11_PORT", default="8000")
        )
    )

    retrieval_mode: RetrievalMode = field(
        default_factory=lambda: _env_first(  # type: ignore[arg-type]
            "MED_RAG_RETRIEVAL_MODE",
            "STAGE12_RETRIEVAL_MODE",
            "STAGE11_RETRIEVAL_MODE",
            default="sample",
        )
    )

    pipeline_backend: PipelineBackend = field(
        default_factory=lambda: _env_first(  # type: ignore[arg-type]
            "MED_RAG_PIPELINE_BACKEND",
            "STAGE12_PIPELINE_BACKEND",
            "STAGE11_PIPELINE_BACKEND",
            default="constrained10",
        )
    )

    documents_mode: RetrievalMode = field(
        default_factory=lambda: _env_first(  # type: ignore[arg-type]
            "MED_RAG_DOCUMENTS_MODE",
            "STAGE12_DOCUMENTS_MODE",
            default=_env_first("MED_RAG_RETRIEVAL_MODE", default="sample"),
        )
    )

    log_dir: Path = field(
        default_factory=lambda: Path(
            _env_first(
                "MED_RAG_LOG_DIR",
                "STAGE12_LOG_DIR",
                "STAGE11_LOG_DIR",
                default=str(MED_RAG_HOME / "data" / "logs"),
            )
        )
    )

    chat_dir: Path = field(
        default_factory=lambda: Path(
            _env_first("MED_RAG_CHAT_DIR", default=str(MED_RAG_HOME / "data" / "chat"))
        )
    )

    ollama_base_url: str = field(
        default_factory=lambda: _env("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: _env("OLLAMA_MODEL", "deepseek-r1:7b")
    )

    session_ttl_seconds: int = field(
        default_factory=lambda: int(
            _env_first("MED_RAG_SESSION_TTL", "STAGE12_SESSION_TTL", "STAGE11_SESSION_TTL", default="86400")
        )
    )
    session_max_turns: int = field(
        default_factory=lambda: int(
            _env_first(
                "MED_RAG_SESSION_MAX_TURNS",
                "STAGE12_SESSION_MAX_TURNS",
                "STAGE11_SESSION_MAX_TURNS",
                default="20",
            )
        )
    )
    query_max_length: int = 2000
    top_k_default: int = 5
    top_k_min: int = 1
    top_k_max: int = 20

    stream_chunk_chars: int = field(
        default_factory=lambda: int(_env("STAGE11_STREAM_CHUNK_CHARS", "32"))
    )

    cors_origins: str = field(
        default_factory=lambda: _env(
            "MED_RAG_CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173",
        )
    )


# Back-compat aliases used by copied stage-11 modules
Stage11Config = MedRagConfig
Stage12Config = MedRagConfig
DEFAULT_CONFIG = MedRagConfig()
