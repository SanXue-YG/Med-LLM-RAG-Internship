"""Stage-0 skeleton checks (no full corpus / no live QA required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

STAGE11 = Path(__file__).resolve().parents[1]


@pytest.fixture()
def boot():
    # Drop colliding upstream modules before bootstrap.
    for name in ("config", "bootstrap", "resources", "app"):
        sys.modules.pop(name, None)
        # Also clear app.* submodules if any were cached from a previous run.
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            sys.modules.pop(key, None)

    sys.path.insert(0, str(STAGE11))
    from app.bootstrap import bootstrap_paths

    return bootstrap_paths(STAGE11)


def test_bootstrap_puts_stage11_first(boot):
    assert boot["stage11"].name.startswith("11")
    assert Path(sys.path[0]).resolve() == boot["stage11"].resolve()
    assert (boot["stage10"] / "src").is_dir()
    assert (boot["stage08"] / "src").is_dir()


def test_config_defaults_sample(boot, monkeypatch):
    monkeypatch.delenv("MED_RAG_RETRIEVAL_MODE", raising=False)
    monkeypatch.delenv("STAGE11_RETRIEVAL_MODE", raising=False)
    # Rebuild frozen defaults after env clear
    import importlib

    import app.config as cfg_mod

    importlib.reload(cfg_mod)
    assert cfg_mod.DEFAULT_CONFIG.retrieval_mode == "sample"
    assert cfg_mod.DEFAULT_CONFIG.pipeline_backend == "constrained10"
    assert cfg_mod.DEFAULT_CONFIG.port == 8000
    assert cfg_mod.DEFAULT_CONFIG.log_dir.name == "logs"


def test_import_app_main(boot):
    from app.main import app

    assert app.title == "Medical RAG API"
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/" in routes


def test_root_endpoint(boot):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["stage"] == "5-done"
    assert body["data"]["retrieval_mode"] == "sample"


def test_stage10_importable_after_bootstrap(boot):
    from app.probe import try_import_stage10

    result = try_import_stage10()
    assert result["ok"] is True, result
    assert result["class"] == "ConstrainedGenerationPipeline"
