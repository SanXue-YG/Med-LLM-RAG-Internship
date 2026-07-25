"""Global exception handler tests (1001 / AppException / 5000)."""

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

    bootstrap_paths(STAGE11)
    return TestClient(app, raise_server_exceptions=False)


def test_validation_error_returns_400_and_code_1001(client: TestClient):
    # Empty message violates min_length=1 → RequestValidationError
    resp = client.post("/api/v1/echo", json={"message": ""})
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 1001
    assert body["message"]
    assert "request_id" in body
    assert body["data"] is not None
    assert "errors" in body["data"]


def test_validation_missing_field_1001(client: TestClient):
    resp = client.post("/api/v1/echo", json={})
    assert resp.status_code == 400
    assert resp.json()["code"] == 1001


def test_echo_success(client: TestClient):
    resp = client.post("/api/v1/echo", json={"message": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["echo"] == "hello"


def test_app_exception_param(client: TestClient):
    resp = client.get("/api/v1/_demo_error", params={"kind": "param"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["code"] == 1001


def test_app_exception_model(client: TestClient):
    resp = client.get("/api/v1/_demo_error", params={"kind": "model"})
    assert resp.status_code == 502
    assert resp.json()["code"] == 4001


def test_unhandled_maps_to_5000(client: TestClient):
    resp = client.get("/api/v1/_demo_error", params={"kind": "internal"})
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == 5000
    assert body["data"]["error_type"] == "RuntimeError"
