# Docker evaluation note (Phase-1 decision)
#
# Chosen delivery: local dual-process (FastAPI + Vite) + docs + zip.
# Reasons not to block on Docker now:
#   1. Ollama is typically a host GPU/service process
#   2. Full Chroma (~70GB) must stay on a volume, not image layers
#   3. Demo target is API visualization for reviewers with local env
#
# Optional future compose sketch (not required for acceptance):
#
# services:
#   api:
#     build: ./backend
#     ports: ["8000:8000"]
#     volumes:
#       - ./data:/app/data
#     environment:
#       OLLAMA_BASE_URL: http://host.docker.internal:11434
#       MED_RAG_RETRIEVAL_MODE: sample
#   web:
#     build: ./frontend
#     ports: ["5173:80"]
#     depends_on: [api]
#
# See docs/部署文档.md §7.
