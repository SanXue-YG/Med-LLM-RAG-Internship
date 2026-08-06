from app.bootstrap import bootstrap_paths

bootstrap_paths()
from paths import index_ready

print("index", index_ready("sample"))
from app.main import app

print("routes", len(app.routes))
from app.deps import get_session_store

s = get_session_store()
rec = s.create()
print("session", rec.session_id)
print("list", len(s.list()))
print("OK")
