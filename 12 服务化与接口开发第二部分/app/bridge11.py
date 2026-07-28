"""Load stage-11 ``app`` (routers + deps singletons) without shadowing stage-12 ``app``.

Stage-11 code uses absolute imports ``from app.…``. We temporarily put stage 11
first on ``sys.path``, import what we need, keep live references, then restore
stage-12 ``app`` modules on ``sys.modules``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from app.bootstrap import bootstrap_paths, stage11_dir, stage12_dir

_CACHE: dict[str, Any] | None = None


def _purge_app_modules() -> dict[str, Any]:
    saved: dict[str, Any] = {}
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            saved[key] = sys.modules.pop(key)
    return saved


def load_stage11(start: Path | None = None) -> dict[str, Any]:
    """Return cached stage-11 handles: deps, config, routers, wiring helpers."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    s12 = stage12_dir(start)
    s11 = stage11_dir(start)
    if not (s11 / "app" / "main.py").is_file():
        raise FileNotFoundError(f"stage 11 app not found under {s11}")

    bootstrap_paths(start)

    # Align stage-11 frozen config with stage-12 env before first s11 import.
    import os

    from app.config import DEFAULT_CONFIG as s12_cfg

    os.environ.setdefault("STAGE11_LOG_DIR", str(s12_cfg.log_dir))
    os.environ.setdefault("STAGE11_HOST", s12_cfg.host)
    os.environ.setdefault("STAGE11_PORT", str(s12_cfg.port))
    os.environ.setdefault("STAGE11_SESSION_TTL", str(s12_cfg.session_ttl_seconds))
    os.environ.setdefault("STAGE11_SESSION_MAX_TURNS", str(s12_cfg.session_max_turns))
    os.environ.setdefault("MED_RAG_RETRIEVAL_MODE", s12_cfg.retrieval_mode)

    saved_s12 = _purge_app_modules()

    for name in ("config", "bootstrap", "resources"):
        sys.modules.pop(name, None)

    s11_root = str(s11.resolve())
    while s11_root in sys.path:
        sys.path.remove(s11_root)
    sys.path.insert(0, s11_root)

    import app.bootstrap as s11_bootstrap  # noqa: E402

    s11_bootstrap.bootstrap_paths(s11)

    # Force reload stage-11 config after env alignment (module may be cached from prior tests).
    import importlib

    import app.config as s11_config_mod  # noqa: E402

    importlib.reload(s11_config_mod)

    from app.api.health import router as health_router  # noqa: E402
    from app.api.qa import router as qa_router  # noqa: E402
    from app import config as s11_config  # noqa: E402
    from app import deps as s11_deps  # noqa: E402
    from app.core.error_codes import ErrorCode  # noqa: E402
    from app.core.exceptions import AppException, register_exception_handlers  # noqa: E402
    from app.core.middleware import RequestContextMiddleware  # noqa: E402
    from app.probe import probe_full_dataset, probe_ollama  # noqa: E402
    from app.schemas.response import PageModel, success_response  # noqa: E402

    _CACHE = {
        "deps": s11_deps,
        "config": s11_config,
        "health_router": health_router,
        "qa_router": qa_router,
        "register_exception_handlers": register_exception_handlers,
        "RequestContextMiddleware": RequestContextMiddleware,
        "success_response": success_response,
        "PageModel": PageModel,
        "AppException": AppException,
        "ErrorCode": ErrorCode,
        "probe_ollama": probe_ollama,
        "probe_full_dataset": probe_full_dataset,
        "stage11": s11,
        "stage12": s12,
    }

    _purge_app_modules()
    sys.modules.update(saved_s12)

    s12_root = str(s12.resolve())
    while s12_root in sys.path:
        sys.path.remove(s12_root)
    sys.path.insert(0, s12_root)
    while s11_root in sys.path:
        sys.path.remove(s11_root)

    return _CACHE


def reset_stage11_cache() -> None:
    """Test helper."""
    global _CACHE
    _CACHE = None


def wire_stage11(app: Any, *, drop_session_get: bool = True) -> dict[str, Any]:
    """Attach stage-11 middleware, exception handlers, health/qa routers.

    When ``drop_session_get`` is True (stage-12 default), remove stage-11's
    ``GET /api/v1/sessions/{id}`` summary so stage-12 can mount full SessionDetail.
    """
    from fastapi.routing import APIRoute

    s11 = load_stage11()
    app.add_middleware(s11["RequestContextMiddleware"])
    s11["register_exception_handlers"](app)

    qa_router = s11["qa_router"]
    if drop_session_get:
        qa_router.routes = [
            r
            for r in qa_router.routes
            if not (
                isinstance(r, APIRoute)
                and r.path == "/api/v1/sessions/{session_id}"
                and "GET" in (r.methods or set())
            )
        ]

    app.include_router(s11["health_router"])
    app.include_router(qa_router)
    return s11
