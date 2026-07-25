"""Structured logging setup (console + optional rotating file under log_dir)."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import DEFAULT_CONFIG, Stage11Config

_CONFIGURED = False


def setup_logging(config: Stage11Config | None = None) -> None:
    """Idempotent logging configuration for the API process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    cfg = config or DEFAULT_CONFIG
    root = logging.getLogger("med_rag_api")
    root.setLevel(logging.INFO)
    root.handlers.clear()

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    log_dir = Path(cfg.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_dir / "api.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    setup_logging()
    if name:
        return logging.getLogger(f"med_rag_api.{name}")
    return logging.getLogger("med_rag_api")
