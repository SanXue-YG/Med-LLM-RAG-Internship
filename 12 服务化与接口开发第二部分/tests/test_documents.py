"""Document catalog API tests (sample sqlite)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

STAGE12 = Path(__file__).resolve().parents[1]
REPO = STAGE12.parent


@pytest.fixture()
def client():
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
    bootstrap_paths(STAGE12)

    from app.main import app

    yield TestClient(app)
    reset_stage11_cache()


def test_list_documents_pagination(client):
    r = client.get("/api/v1/documents", params={"page": 1, "page_size": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total"] == 1000
    assert len(data["items"]) == 5
    assert "doc_id" in data["items"][0]
    assert data["items"][0]["doc_id"].startswith("PMC")


def test_list_documents_title_q(client):
    r = client.get("/api/v1/documents", params={"q": "Plasmodium", "page_size": 10})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] >= 1
    assert all("Plasmodium" in (it.get("title") or "") for it in data["items"])


def test_get_document_ok(client):
    r = client.get("/api/v1/documents/PMC176545")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["doc_id"] == "PMC176545"
    assert "Plasmodium" in data["title"]
    assert "answer_preview" not in data


def test_get_document_missing_3001(client):
    r = client.get("/api/v1/documents/PMC_DOES_NOT_EXIST")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == 3001
    assert body["message"] == "document not found"
    assert body["data"]["detail"]["doc_id"] == "PMC_DOES_NOT_EXIST"


def test_route_miss_not_3001(client):
    """Generic HTTP 404 must not pollute DOC_NOT_FOUND semantics."""
    r = client.get("/api/v1/no-such-route-xyz")
    assert r.status_code == 404
    assert r.json()["code"] != 3001


def test_root_stage(client):
    r = client.get("/")
    assert r.json()["data"]["stage"] == "12-6"
    assert r.json()["data"]["documents"] == "catalog"


def test_document_store_unit(tmp_path, client):
    from app.services.document_store import DocumentStore

    # Uses real sample path via default mode (client fixture already bootstrapped)
    store = DocumentStore(mode="sample")
    doc = store.get_document("PMC176545")
    assert doc is not None and doc.doc_id == "PMC176545"
    assert store.get_document("NOPE") is None
    items, total = store.list_documents(page=1, page_size=3)
    assert total == 1000 and len(items) == 3
