from app.bootstrap import bootstrap_paths

bootstrap_paths()
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
sid = "316389ab-6117-473d-81f6-de7c0f0e65c0"
r = c.get(f"/api/v1/sessions/{sid}")
print("status", r.status_code)
body = r.json()
print("top keys", body.keys())
data = body.get("data")
print("data type", type(data))
if isinstance(data, dict):
    print("data keys", data.keys())
    print("title", data.get("title"))
    turns = data.get("turns") or []
    print("n turns", len(turns))
    if turns:
        print("turn keys", turns[0].keys())
        ans = turns[0].get("answer")
        print("answer type", type(ans), "len", len(ans or ""))
        print("head", repr((ans or "")[:120]))
else:
    print("data", data)
