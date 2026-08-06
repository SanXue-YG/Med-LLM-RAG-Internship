from fastapi.testclient import TestClient

from app.bootstrap import bootstrap_paths

bootstrap_paths()
from app.main import app

c = TestClient(app)
print("GET /", c.get("/").json()["code"])
print("GET /health", c.get("/health").status_code)
print("GET /api/v1/sessions", c.get("/api/v1/sessions").json())
print("GET /api/v1/ingest/status", c.get("/api/v1/ingest/status").json()["data"]["ready"])
r = c.post("/api/v1/sessions")
print("POST session", r.json()["data"]["session_id"][:8])
print("OK")
