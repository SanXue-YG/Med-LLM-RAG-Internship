"""Reproduce pipeline load failure and print the real exception."""
from __future__ import annotations

import traceback

from app.bootstrap import bootstrap_paths

bootstrap_paths()

from paths import index_ready
from app.config import DEFAULT_CONFIG
from app.services.rag_service import RagService

print("index_ready:", index_ready(DEFAULT_CONFIG.retrieval_mode))
print("mode:", DEFAULT_CONFIG.retrieval_mode)
print("backend:", DEFAULT_CONFIG.pipeline_backend)

svc = RagService(DEFAULT_CONFIG)
try:
    p = svc.ensure_pipeline()
    print("LOADED:", type(p))
except Exception as exc:
    print("TYPE:", type(exc).__name__)
    print("MSG:", exc)
    detail = getattr(exc, "detail", None)
    print("DETAIL:", detail)
    traceback.print_exc()
