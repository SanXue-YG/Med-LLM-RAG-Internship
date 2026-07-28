# 部署与 API 调用说明（阶段 0–4）

> 日常开发走 **sample**。全量仿真见阶段 5 / [`api-ops-full.ipynb`](../notebooks/api-ops-full.ipynb)。

## 1. 环境

- Conda：**`med-rag-verify`**（01–12 共用）
- 依赖：[`requirements.txt`](../requirements.txt)（相对 11 主要新增 `python-dotenv`）
- Ollama：本机可访问（默认 `http://127.0.0.1:11434`，模型见 `.env.example`）
- 样本资产：`Dataset/chroma/chroma_db`、`Dataset/documents/sample/`（✅）

```powershell
conda activate med-rag-verify
cd "12 服务化与接口开发第二部分"
pip install -r requirements.txt
copy .env.example .env   # 按需改端口 / 模式
```

## 2. 本地启动

```powershell
python scripts/run_api.py --no-reload
```

- 根：`GET http://127.0.0.1:8000/` → `stage=12-4`
- Swagger：`/docs` · ReDoc：`/redoc`
- 健康：`GET /health`（阶段 11）

冒烟 notebook：[`notebooks/api-ops-smoke.ipynb`](../notebooks/api-ops-smoke.ipynb)（C0–C4）。

## 3. 环境变量清单

| 变量 | 默认 | 说明 |
|------|------|------|
| `STAGE12_HOST` / `STAGE11_HOST` | `127.0.0.1` | 监听地址 |
| `STAGE12_PORT` / `STAGE11_PORT` | `8000` | 端口 |
| `MED_RAG_RETRIEVAL_MODE` | `sample` | 检索库 sample/full；**改后须重启进程** |
| `STAGE12_DOCUMENTS_MODE` | `sample` | `/documents` 读哪份 sqlite |
| `STAGE12_PIPELINE_BACKEND` | `constrained10` | 生成管线 |
| `STAGE12_LOG_DIR` / `STAGE11_LOG_DIR` | `<stage12>/outputs/logs` | `qa_calls.jsonl` 与 api 日志 |
| `STAGE12_SESSION_TTL` | `3600` | 会话 TTL（秒） |
| `STAGE12_SESSION_MAX_TURNS` | `10` | 每会话最大轮数 |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama |
| `OLLAMA_MODEL` | `deepseek-r1:7b` | 模型名 |
| `MED_RAG_DATASET_ROOT` | `<repo>/Dataset` | 可选，改大数据根目录 |

加载：`app/config.py` 用 `python-dotenv` 读阶段目录 `.env`（**不覆盖**已有进程环境变量）。

## 4. API 一览

### 会话（阶段 1）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/sessions` | 显式开桌 |
| GET | `/api/v1/sessions/{id}` | 完整 `turns`；无效 → **3002** |
| DELETE | `/api/v1/sessions/{id}` | 撤桌；无效 → **3002** |

与 `POST /api/v1/qa` **共用** `MemorySessionStore`。QA 对无效 id **自动新建** ≠ GET/DELETE 的 3002。

### 运营统计（阶段 2）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/stats/qa` | 聚合同一 `qa_calls.jsonl` |
| GET | `/api/v1/stats/index` | `chunk_count` ≠ `document_count` |
| GET | `/api/v1/stats/health` | llm / vector / database=`skipped` / api |

### 文档（阶段 3）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/documents` | `PageModel`；可选 `q` |
| GET | `/api/v1/documents/{doc_id}` | `doc_id`=**pmcid**；缺失 → **3001** |

路由未命中 HTTP 404 → 业务码 **1001**（不再误用 3001）。

### 问答 / 健康（阶段 11，经 bridge 挂载）

- `POST /api/v1/qa` · `POST /api/v1/qa/stream`（伪 SSE）
- `GET /health` · `GET /ready`

## 5. 调用示例

### curl

```powershell
# 开桌
curl -s http://127.0.0.1:8000/api/v1/sessions

# 问答（把 SESSION 换成上一步 session_id）
curl -s -X POST http://127.0.0.1:8000/api/v1/qa `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"What is Plasmodium falciparum transcriptome?\",\"session_id\":\"SESSION\"}"

# 历史 / 统计 / 文档
curl -s http://127.0.0.1:8000/api/v1/sessions/SESSION
curl -s http://127.0.0.1:8000/api/v1/stats/qa
curl -s "http://127.0.0.1:8000/api/v1/documents?page=1&page_size=5"
curl -s http://127.0.0.1:8000/api/v1/documents/PMC176545
```

### httpx

```python
import httpx

base = "http://127.0.0.1:8000"
with httpx.Client(base_url=base, timeout=120.0) as client:
    sid = client.post("/api/v1/sessions").json()["data"]["session_id"]
    qa = client.post("/api/v1/qa", json={"query": "hello", "session_id": sid}).json()
    hist = client.get(f"/api/v1/sessions/{sid}").json()
    stats = client.get("/api/v1/stats/index").json()
    doc = client.get("/api/v1/documents/PMC176545").json()
    print(sid, qa["code"], hist["data"]["turn_count"], stats["data"]["document_count"])
```

## 6. Postman

1. Import [`postman/MedRAG_API.postman_collection.json`](../postman/MedRAG_API.postman_collection.json)
2. 集合变量：`baseUrl`（默认 `http://127.0.0.1:8000`）、`docId`（默认 `PMC176545`）
3. 先跑 **POST /api/v1/sessions**（Tests 脚本会写入 `sessionId`），再跑 QA / GET session
4. 浏览 `/docs` 核对 tags：`health` / `qa` / `sessions` / `stats` / `documents`

## 7. 与阶段 11 的差异

| 项 | 11 | 12 |
|----|----|----|
| 会话 | 仅 QA 内摘要 GET | 完整 CRUD；GET 返回完整 `answer` |
| 统计 / 文档 | 无 | `/stats/*` · `/documents` |
| `.env` | 仅 `os.getenv` | dotenv + `.env.example` |
| `3001` | 曾被通用 404 占用 | **仅**文档缺失；路由 404 → 1001 |
| 单例 | 本进程 | bridge11 共用 Store / QACallLogger |

## 8. 文档索引构建

```powershell
python scripts/build_documents_index.py --mode sample   # 一般不必重跑
python scripts/build_documents_index.py --mode full --status
```

- 样本：`Dataset/documents/sample/documents_sample.sqlite`（✅ 1000）
- 全量：`Dataset/documents/full/documents_full.sqlite`（✅ 4,557,627）

## 9. 切换 full（预告 · 阶段 5）

```powershell
# .env
MED_RAG_RETRIEVAL_MODE=full
STAGE12_DOCUMENTS_MODE=full
# 然后重启 API；用 api-ops-full.ipynb 做全量仿真（勿在每请求中途换库）
```
