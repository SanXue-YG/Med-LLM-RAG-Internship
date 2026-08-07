# Runtime data root for Med-RAG (self-contained)

Place assets here only — never rely on repo-root `Dataset/` at runtime.

## sample vs full（本目录职责）

| 侧 | 角色 | 本目录内容 |
|----|------|------------|
| **sample** | 接近实际用户交互：可空库 + 回形针增量 | `chroma/chroma_db`、`processed/chunks_sample.jsonl`、`documents/sample/`、`raw_uploads/` |
| **full** | 预建大数据集迁入后供问答 | `chroma/chroma_db_full`、`bm25/bm25_full`、`documents/full/` 等（需自行导入） |

**注意**：UI / `POST /api/v1/ingest/upload` **无论检索模式是 sample 还是 full，都只更新 sample 侧**。原件落在 `raw_uploads/`。full 索引不能靠当前 Demo 上传刷新。

## Layout

```text
data/
├── chroma/chroma_db/          # sample Chroma（预建或 ingest 写入）
├── chroma/chroma_db_full/     # full Chroma（迁入）
├── bm25/bm25_full/            # 仅 full 离线 BM25
├── documents/sample|full/     # documents_*.sqlite
├── processed/chunks_sample.jsonl
├── processed/oa_comm_*.jsonl  # full 重建原料（可选挂载）
├── lexicons/medical_synonyms.json
├── raw_uploads/               # 回形针原始 XML/JSONL
├── chat/                      # 会话（与 sample/full 无关）
└── logs/qa_calls.jsonl
```

## Bootstrap sample from this machine

```powershell
# From repo root (example)
Copy-Item Dataset\processed\chunks_sample.jsonl Med-RAG\data\processed\ -Force
Copy-Item -Recurse Dataset\chroma\chroma_db Med-RAG\data\chroma\chroma_db -Force
Copy-Item Dataset\documents\sample\documents_sample.sqlite Med-RAG\data\documents\sample\ -Force
```

Or use the UI paperclip / `POST /api/v1/ingest/upload`（写入 sample）。

**深入说明（对照表、流程图、Drive 迁移）**：见 [`../docs/数据存储与导入参考.md`](../docs/数据存储与导入参考.md)。  
约定共享备份：[Google Drive — Dataset](https://drive.google.com/drive/folders/1uK-2nbpOAWH61pWWrArpR8fdUzUihZ7H?usp=sharing)。
