"""Health / ready endpoint tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STAGE11 = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client():
    for key in list(sys.modules):
        if key == "app" or key.startswith("app."):
            sys.modules.pop(key, None)
    sys.path.insert(0, str(STAGE11))
    from app.bootstrap import bootstrap_paths
    from app.main import app
    from app.state import RUNTIME

    bootstrap_paths(STAGE11)
    RUNTIME.pipeline_loaded = False
    RUNTIME.pipeline_mode = None
    RUNTIME.last_error = None
    return TestClient(app)


def test_health_ok(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == "ok"
    assert "request_id" in body
    assert resp.headers.get("X-Request-Id") == body["request_id"]


def test_health_accepts_incoming_request_id(client: TestClient):
    resp = client.get("/health", headers={"X-Request-Id": "fixed-rid-123"})
    assert resp.status_code == 200
    assert resp.json()["request_id"] == "fixed-rid-123"
    assert resp.headers["X-Request-Id"] == "fixed-rid-123"


def test_ready_not_loaded_yet(client: TestClient):
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["ready"] is False
    assert body["data"]["pipeline_loaded"] is False


def test_root_uses_response_model(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["stage"] == "5-done"
