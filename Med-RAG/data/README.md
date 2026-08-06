# Runtime data root for Med-RAG (self-contained)

Place assets here only — never rely on repo-root `Dataset/` at runtime.

## Layout

```text
data/
├── chroma/chroma_db/          # sample Chroma (pmc_oa_comm_sample)
├── chroma/chroma_db_full/     # optional full
├── bm25/bm25_full/            # optional full BM25 shards
├── documents/sample|full/     # documents_*.sqlite
├── processed/chunks_sample.jsonl
├── processed/oa_comm_slim.jsonl   # optional
├── lexicons/medical_synonyms.json
├── raw_uploads/               # ingest uploads
├── chat/                      # file-backed sessions
└── logs/qa_calls.jsonl
```

## Bootstrap sample from this machine

```powershell
# From repo root (example)
Copy-Item Dataset\processed\chunks_sample.jsonl Med-RAG\data\processed\ -Force
Copy-Item -Recurse Dataset\chroma\chroma_db Med-RAG\data\chroma\chroma_db -Force
Copy-Item Dataset\documents\sample\documents_sample.sqlite Med-RAG\data\documents\sample\ -Force
```

Or use the UI paperclip / `POST /api/v1/ingest/upload` with a small XML/JSONL.
