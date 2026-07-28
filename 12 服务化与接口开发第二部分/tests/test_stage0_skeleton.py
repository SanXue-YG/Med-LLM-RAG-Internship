"""Stage-0 skeleton checks (sample index build covered separately / notebook C0.5)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

STAGE12 = Path(__file__).resolve().parents[1]
REPO = STAGE12.parent


@pytest.fixture()
def boot():
    for name in ("config", "bootstrap", "resources", "app"):
        sys.modules.pop(name, None)
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            sys.modules.pop(key, None)

    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(STAGE12))
    from app.bootstrap import bootstrap_paths
    from app.bridge11 import reset_stage11_cache

    reset_stage11_cache()
    return bootstrap_paths(STAGE12)


def test_bootstrap_puts_stage12_first(boot):
    assert boot["stage12"].name.startswith("12")
    assert Path(sys.path[0]).resolve() == boot["stage12"].resolve()
    assert (boot["stage11"] / "app" / "main.py").is_file()
    assert (boot["stage10"] / "src").is_dir()


def test_root_and_health(boot):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["stage"] == "12-4"
    assert body["data"]["singletons"] == "stage11-deps"
    assert body["data"]["sessions"] == "crud"
    assert body["data"]["stats"] == "qa+index+health"
    assert body["data"]["documents"] == "catalog"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["code"] == 0


def test_deps_are_stage11_singletons(boot):
    from app import deps
    from app.bridge11 import load_stage11

    s11 = load_stage11()
    assert deps.get_session_store() is s11["deps"].get_session_store()
    assert deps.get_qa_logger() is s11["deps"].get_qa_logger()
