# 12 服务化与接口开发第二部分 — 执行计划

> **状态：🔄 阶段 0–4 完成**（样本契约齐；**待阶段 5** 全量仿真 / 阶段 6 收尾）
>
> **本阶段范围（任务书）**：在 11 FastAPI 骨架之上，补齐 **会话管理 API**、**运营统计 API**、**文档管理 API**；完成 **测试 / OpenAPI / `.env` / 部署与调用示例**。
>
> **上游依赖**：
> - 11：`app/`（`ResponseModel`、错误码、`/qa`、`MemorySessionStore`、`qa_logger`、`/health`·`/ready`）
> - 10/08：RAG 流水线（问答仍走 11 `RagService`）
> - 02/06/Dataset：文档元数据（slim / Chroma count）供统计与文档列表

---

## 任务书目标对照

| 任务书要求 | 本阶段交付 |
|------------|------------|
| 会话：创建 / 获取历史 / 删除 / 添加消息 | `POST/GET/DELETE /api/v1/sessions` 等；问答接口自动 `append` |
| 多轮对话上下文 | 强化 11 SessionStore；可选历史注入（延续 11 MVP 策略） |
| 运营统计：问答次数、耗时、成功率 | `GET /api/v1/stats/qa`（读 JSONL / 内存聚合） |
| 文档总数、索引大小、增量更新次数 | `GET /api/v1/stats/index` |
| 组件健康（LLM、向量库、数据库） | `GET /api/v1/stats/health`（扩展 11 probe） |
| `DocumentIn` 模型 + 列表 / 按 id 查询 | `GET /api/v1/documents`、`GET /api/v1/documents/{doc_id}` |
| 单元/集成测试（Postman） | `tests/` + `postman/MedRAG_API.postman_collection.json` |
| OpenAPI（Swagger） | FastAPI 自带 `/docs`；补充描述与示例 |
| `.env` 环境变量 | `.env.example` + `python-dotenv` / pydantic-settings |
| 部署文档与 API 调用示例 | `docs/部署与API调用说明.md` |

---

## 关键约束与设计决策（启动前）

| 项 | 决策 | 说明 |
|----|------|------|
| 代码落点 | **12 新建目录；bootstrap 导入 11 的 `app` 包**；本周新增 router/service 写在 12 | 独立交付目录；**禁止**再 new 一套 SessionStore / QACallLogger，否则与 `/qa` 数据分裂 |
| 会话 Store | **复用 11 同一单例** `deps.get_session_store()`；在 11 或 12 包装层 **补 `delete()`**（Protocol 同步扩展） | 11 已有 `create/get/require/append`，**无** `delete`/`list` |
| 会话 HTTP | 补 `POST` 创建、`DELETE` 删除；**增强**已有 `GET /sessions/{id}`（可迁到 `sessions` router） | 11 已在 `qa.py` 实现 GET（摘要）；任务书未要求会话列表 → **不做** `GET /sessions` 列表 |
| 会话消息模型 | **对外可映射为 role 消息；对内仍是 `SessionTurn(query, answer)`** | 11 一轮 QA = **一条 turn**，不是两条独立 message；见下方「上游接口事实」 |
| `/qa` 与 3002 | **保持 11 策略**：QA 路径过期/缺失 → **自动新建**；严格 GET/DELETE → **3002** | 写进 OpenAPI / 部署文档，避免验收口径打架 |
| 「添加消息」 | **仅由 `/qa`（及 stream）自动 `append(SessionTurn)`**；不强制公开 `POST .../messages` | 满足任务书「由问答接口自动调用」；可选内部/测试辅助方法 |
| 会话持久化 | 首版仍 **进程内**；可选落盘 JSON | 任务书未要求 DB；Protocol 预留后续 sqlite |
| 运营统计数据源 | **读与 11 相同的** `qa_calls.jsonl`（`config.log_dir`）；可选内存计数器作补充 | 12 的 `LOG_DIR` 必须与问答写入路径一致，否则 stats 恒为空 |
| 索引统计 | `chunk_count`←Chroma；`document_count`←**documents sqlite COUNT**；目录体积←persist | 二者勿混；增量次数 MVP=0+note |
| 文档索引 | **定稿建全库 + 样本 sqlite**（`Dataset/documents/`） | 兼 `/documents` 与未来打包替代 06 slim 回查 |
| 样本资产落点 | **复制**进 Dataset（不改 03/04）；`chunks_sample` ✅ 已复制 | 不进 Git；README 写来源 |
| `3001` 语义 | 未命中 → `AppException(DOC_NOT_FOUND)` | 收紧通用 404→3001 |
| 认证 | 预留 `2001` | 与 11 一致 |
| 本阶段边界 | 不做前端 / 在线上传入库 / K8s / 会话列表 | **做**离线全库文档索引；阶段 5 **完整接入** full sqlite |

### 全库文档索引（本周定稿要做）

> 依据 06 `SlimMetadataLookup`（`pub_year`/`journal`）与 12 `DocumentIn`。  
> 说明：[`Dataset/documents/README.md`](../Dataset/documents/README.md) · [`Dataset/打包资产清单.md`](../Dataset/打包资产清单.md)

| 产物 | 路径 | 何时用 |
|------|------|--------|
| 样本索引 | `documents/sample/documents_sample.sqlite` | 阶段 0–4 契约 |
| 全库索引 | `documents/full/documents_full.sqlite` | 阶段 5 + 打包（**运行时单库**） |
| 断点进度 | `documents/full/progress_full.json` | 全量构建中途可续跑 |
| 字段 | pmcid, title, abstract, journal, pub_year, pub_date, … | 见 documents README |

> **构建**：对标 BM25 的「流式 + 断点」，但用 **逻辑分片**（按批 upsert + 各 mode 目录下 `progress_*.json`），**sample/full 分目录**。详见 [`Dataset/documents/README.md`](../Dataset/documents/README.md)。

补丁：[`（未来优化）打包后数据更新/schedule.md`](../（未来优化）打包后数据更新/schedule.md)。

### 样本资产复制进 Dataset

> **原则**：只复制、不移动；不进 Git；README 可重建；新代码读 `dataset_paths`。

| 资产 | 状态 | Dataset 路径 |
|------|------|--------------|
| `chunks_sample.jsonl` | ✅ **2026-07-27 已复制**（源 03；原文件保留） | `processed/chunks_sample.jsonl` |
| documents sample/full sqlite | ✅ **sample 1000**；✅ **full 4,557,627**（2026-07-27） | `documents/{sample,full}/documents_*.sqlite` |
| 样本 Chroma / 全量检索资产 | ✅ 已在 | 见 Dataset README |

**阶段 0 状态（✅ 出门标准已满足）**

1. ✅ `dataset_paths`：`CHUNKS_SAMPLE_JSONL` / `DOCUMENTS_*_SQLITE`  
2. ✅ `06 resolve_chunks_path("sample")` 优先 Dataset  
3. ✅ `scripts/build_documents_index.py --mode sample|full`  
4. ✅ **smoke C0.5** → `documents_sample.sqlite`（1000 篇）  
5. ✅ **full F0** → `documents/full` 已完成（4,557,627 篇；逻辑分片单库，非物理多 shard）  
6. DocumentStore 读 sample sqlite → 阶段 3；full 路径已可用  



### 上游接口事实（内容层对齐用）

| 上游（11 已实现） | 可调用形态 | 本周注意 |
|-------------------|------------|----------|
| `MemorySessionStore` | `create` / `get` / `require` / `append`；**无 delete/list** | 12 必须补 `delete`；与 `/qa` **共用单例** |
| `SessionTurn` | `query`, `answer`, `created_at`, `meta` | **不是** `role/content`；一轮问答 = 1 turn |
| `GET /api/v1/sessions/{id}` | `qa.get_session`：`require`；返回 `turns[{query, answer_preview}]` | 可增强为完整 history；无效 → **3002** |
| `/qa` 会话策略 | 无 id 或过期 → **自动 create**；成功后 `append` 一轮 | 与严格 GET 的 3002 **故意不一致**（11 报告已写） |
| `QACallLogger` | `outputs/logs/qa_calls.jsonl`；字段含 `status`/`latency_ms`/`code`/`request_id`… | stats/qa 按行聚合；耗时单位是 **ms** |
| `/health` · `/ready` · `probe_ollama` / `probe_full_dataset` | 进程探活 + 资源自检 | stats/health **组合复用**，不替代原 `/health` |
| `PageModel` | `items/total/page/page_size` | 业务路由尚未使用 → **documents 列表首次落地** |
| `ErrorCode.DOC_NOT_FOUND=3001` | 预留；现被通用 HTTP 404 handler 映射 | 上文档 API 时 **收紧 404 映射** |
| `Stage11Config` | 仅 `os.getenv`，**无** `.env` 文件 | 12 用 dotenv 加载进同名/兼容 env 即可 |
| slim / 样本字段 | `pmcid`, `pmid`, `title`, `abstract`, `journal`, `pub_year`, `pub_date`… | `DocumentIn.doc_id` ← **`pmcid`**（勿虚构另一套 id） |

### 与 11 已有能力的衔接

| 11 已有 | 12 增量 |
|---------|---------|
| `MemorySessionStore` + `GET /sessions/{id}`（摘要） | `POST` 创建、`DELETE`；Store.`delete`；GET 历史口径对齐任务书 |
| `/qa` 内 `append(SessionTurn)` | 文档写清「添加消息 = 自动 append 一轮」；不另造双写 |
| `qa_logger` JSONL | `GET /stats/qa` 聚合该文件（路径共享） |
| `/health` · `/ready` · probe | `GET /stats/health` 汇总组件；保留原探活路径 |
| `PageModel` / `3001` 预留 | documents 列表 + 按 id；修正 404→3001 污染 |
| `/docs` OpenAPI | 补 tags、示例、`.env`、Postman、部署文档 |

### 会话对外模型（定稿）

避免「任务书 role 消息」与「11 turn 存储」两套口径打架：

| 方案 | 说明 | 本周选择 |
|------|------|----------|
| A. 对外仍返回 `turns[{query, answer, …}]` | 与 Store 一致；OpenAPI 注明一轮=一问一答 | ✅ **默认**（改动小、验收清晰） |
| B. 适配为 `messages[{role, content}]` | 每 turn 拆成 user + assistant 两条 | 可选；若做，**验收按 2 轮 → 4 条 messages** |

验证用例按 **方案 A**：两轮 QA → Store / GET 中 **`turn_count=2`**（不是 4 条独立 message）。

### DocumentIn ↔ documents 索引字段

| API / 回查 | sqlite 列 | 备注 |
|------------|-----------|------|
| `doc_id` | `pmcid` | 主键 |
| title / abstract / journal / pub_date | 同名 | 12 `/documents` |
| pub_year / journal | 同名 | 06 recency/authority；打包替代 slim |

### 响应字段映射（统计）

| API 字段 | 来源 |
|----------|------|
| `total_calls` / `success_count` / `failure_count` | JSONL 行数；`status=="ok"` / `"error"` |
| `success_rate` | `success_count / total_calls`（0 调用时约定 0 或 null，文档写清） |
| `avg_latency_seconds` | `mean(latency_ms) / 1000`（JSONL 为 ms） |
| `chunk_count` | Chroma collection `.count()` |
| `document_count` | 样本索引条数 **或** `null` + `note`（勿把 chunk 数当成篇数） |
| `index_size_bytes` | Chroma persist 目录磁盘占用 |
| `incremental_update_count` | MVP **0** + `note` |
| health.`llm` | `probe_ollama` |
| health.`vector_db` | persist 可读 + 抽样 count / `probe_full_dataset` 子集 |
| health.`database` | **`skipped`**（无独立 DB；JSONL ≠ database） |
| health.`api` | 进程自身 ok |

---

## 端到端数据流

```
Client
  ├─ POST /api/v1/sessions              → 共用 SessionStore.create
  ├─ POST /api/v1/qa (+ session_id)     → RagService → append(SessionTurn)  # 一轮=一问一答
  │                                         过期/缺失 id → 自动新建（不抛 3002）
  ├─ GET  /api/v1/sessions/{id}         → require → turns 历史（无效 → 3002）
  ├─ DELETE /api/v1/sessions/{id}       → store.delete（幂等策略见阶段 1）
  ├─ GET  /api/v1/stats/qa              → 聚合同一 qa_calls.jsonl
  ├─ GET  /api/v1/stats/index|health    → Chroma/磁盘 + probe；database=skipped
  └─ GET  /api/v1/documents[/{doc_id}]  → DocumentStore（doc_id=pmcid）；未命中 3001
```

---

## 模块设计

### 目录结构（规划）

```text
12 服务化与接口开发第二部分/
├── 任务.txt
├── schedule.md
├── .env.example
├── requirements.txt                 # 继承 11 + python-dotenv（若需）
├── app/
│   ├── __init__.py
│   ├── main.py                      # 挂载 sessions / stats / documents + 复用 11 qa/health
│   ├── config.py                    # 读 .env；兼容 11 配置项
│   ├── bootstrap.py                 # path → 11 + 上游阶段
│   ├── api/
│   │   ├── sessions.py
│   │   ├── stats.py
│   │   └── documents.py
│   ├── schemas/
│   │   ├── session.py
│   │   ├── stats.py
│   │   └── document.py              # DocumentIn / DocumentOut
│   └── services/
│       ├── session_service.py       # 薄封装；核心仍用 11 MemorySessionStore 单例
│       ├── stats_service.py         # QA / index / health 聚合
│       └── document_store.py        # 列表与按 id 查询（doc_id=pmcid）
├── data/                            # 仅脚本产物缓存（可选）；权威样本在 Dataset/
├── postman/
│   └── MedRAG_API.postman_collection.json
├── notebooks/
│   ├── api-ops-smoke.ipynb          # 样本主轨：C0/C0.5（含建 sample 索引）→ C1…C4
│   └── api-ops-full.ipynb           # F0 全量索引构建（可观察进度）→ 阶段 5 全量仿真
├── scripts/
│   ├── run_api.py
│   ├── build_documents_index.py     # slim→sqlite；批提交 + progress 断点续建
│   └── run_full_ops_smoke.py        # 阶段 5 全量连通 / 可被 api-ops-full 调用
├── tests/
│   ├── test_sessions.py
│   ├── test_stats.py
│   ├── test_documents.py
│   └── test_integration_api.py
└── docs/
    └── 部署与API调用说明.md
```

### API 一览（本周新增 / 对齐）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/sessions` | 创建会话（显式开桌） |
| GET | `/api/v1/sessions/{session_id}` | **已有**；增强返回完整 `turns`（无效 → `3002`） |
| DELETE | `/api/v1/sessions/{session_id}` | 删除；幂等：已不存在可 3002 或 `code=0` 写清一种 |
| GET | `/api/v1/stats/qa` | 问答次数、平均耗时、成功率 |
| GET | `/api/v1/stats/index` | chunk/文档规模、索引大小、增量次数（占位） |
| GET | `/api/v1/stats/health` | LLM / 向量库 / 数据库(skipped) / API |
| GET | `/api/v1/documents` | 分页列表（`PageModel`）；可选 `q` |
| GET | `/api/v1/documents/{doc_id}` | 按 **pmcid** 查询；不存在 → `3001` |

> **不做（本周）**：`GET /api/v1/sessions` 列表；公开 `POST .../messages`（添加消息仅 `/qa` 自动 append）。  
> 11 已有并继续挂载：`GET /health`、`GET /ready`、`POST /api/v1/qa`、`POST /api/v1/qa/stream`。

### 核心模型（草案 · 已对齐 11）

```python
class DocumentIn(BaseModel):
    doc_id: str          # = pmcid
    title: str
    abstract: str | None = None
    journal: str | None = None
    pub_date: str | None = None
    # 可选：pmid, pub_year


class SessionCreateResponse(BaseModel):
    session_id: str
    created_at: str  # ISO；内部 Store 仍可用 float epoch


class SessionTurnOut(BaseModel):
    """与 11 SessionTurn 对齐：一轮 QA = 一条。"""
    query: str
    answer: str
    created_at: str
    meta: dict | None = None


class SessionDetail(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    turn_count: int
    turns: list[SessionTurnOut]


class QAStats(BaseModel):
    total_calls: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_latency_seconds: float  # 由 JSONL latency_ms / 1000


class IndexStats(BaseModel):
    document_count: int | None  # 篇级；样本索引条数或 null
    chunk_count: int | None     # Chroma count（勿与 document_count 混用）
    index_size_bytes: int | None
    incremental_update_count: int  # MVP = 0
    note: str | None = None


class ComponentHealth(BaseModel):
    name: str  # llm | vector_db | database | api
    status: Literal["ok", "degraded", "down", "skipped"]
    detail: dict | None = None
```

---

## 分阶段执行

> **工作流（对齐 09 / 11）**  
> - **样本主轨**：`api-ops-smoke.ipynb`（**C0 → C4**）贯穿阶段 0–4；**阶段 0 必须在 smoke 里建好 `documents_sample.sqlite`**，供阶段 1–4 文档 API / 契约验证。  
> - **全量索引构建入口**：`api-ops-full.ipynb` **F0**（可视化进度：读 `documents/full/progress_full.json`）；也可 CLI 后台跑同一 `build_documents_index.py --mode full`。  
> - **并行节奏**：**不必等 full 建完再写 1–4**——sample 就绪即可进会话/统计/文档代码；full 可过夜或后台续跑。  
> - **阶段 5 门槛**：检索 full 资产齐 + **documents/full 已 completed**（✅ 2026-07-27）→ 再跑全量仿真。  
> - **阶段 6** = 交付收尾。  
> 每完成一小阶段：**勾选 checklist → 填写完成说明 / 实现说明 → 补齐对应 notebook → 再进下一阶段**。

```text
0 骨架+.env → smoke C0/C0.5（sample ✅）→ full F0 ✅（documents/full 已齐）
1 会话 → C1 · 2 统计 → C2 · 3 文档(sample) → C3 · 4 测试/文档 → C4
5 api-ops-full 全量仿真（Chroma/BM25/documents_full + Ollama）
6 交付收尾
```

### 阶段 0：环境与骨架 + Dataset 样本复制 + 文档索引构建 ✅

- [x] 创建目录结构（`app/`、`scripts/`、`tests/`、`notebooks/`、`outputs/`、`postman/`、`docs/`）
- [x] `requirements.txt`（复用 11 + `python-dotenv`）
- [x] `.env.example`（兼容 11 + `STAGE12_*` 别名）+ dotenv 加载
- [x] `bootstrap`：stage12 为 `app`；经 `bridge11` 挂载 11 的 health/qa 与 deps 单例
- [x] `main.py`：FastAPI；include 11 health/qa；预留 sessions/stats/documents OpenAPI tags
- [x] **单例策略**：`app.deps` → `bridge11.load_stage11()["deps"]`（与 `/qa` 同一 Store / Logger）
- [x] **样本复制**：`chunks_sample.jsonl` → `Dataset/processed/`（2026-07-27；03 原文件保留）
- [x] `dataset_paths`：`CHUNKS_SAMPLE_JSONL` / `DOCUMENTS_*_SQLITE`
- [x] `06 resolve_chunks_path("sample")` 优先 Dataset
- [x] `scripts/build_documents_index.py --mode sample|full`（批提交 + `progress_{mode}` 断点）
- [x] `Dataset/documents/README.md` 对齐逻辑分片与 `manifest_{mode}` 命名
- [x] `scripts/run_api.py` 可启动
- [x] Notebook **C0**（`api-ops-smoke.ipynb`）
- [x] Notebook **C0.5**：已构建 **`documents_sample.sqlite`（1000 篇）**
- [x] **`api-ops-full.ipynb` · F0**：全量建库完成 → `documents/full/manifest_full.status=completed`（**4,557,627** 篇 · ≈11.5 GB · ≈134 s）
- [x] （原阶段 5 前硬门槛）`documents/full` → `manifest_full.status=completed` ✅ **2026-07-27**

> **阶段 0 出门标准（进 1–4）**：✅ 骨架可起 + **sample 索引已落盘**。  
> **全量索引**：✅ 已完成；阶段 5 仿真可直接挂 `documents/full`（阶段 1–4 仍用 sample）。

**阶段 0 完成说明**

> 搭好 12 骨架：`bootstrap` + `bridge11` 复用 11 的 `/health` `/qa` 与 deps 单例；`.env.example` + dotenv；`run_api` 可起。  
> **C0.5** 产出 `Dataset/documents/sample/documents_sample.sqlite`（1000 篇）及同目录 `manifest_sample.json`。  
> **F0** 已完成：`Dataset/documents/full/documents_full.sqlite`（**4,557,627** 篇）+ `manifest_full.json`（`status=completed`）。形态为 **逻辑分片单库**（批 upsert + `progress_full.json` 断点），**无** BM25 式多物理 shard 文件。`tests/test_stage0_skeleton.py` 3 passed。

**阶段 0 实现说明（代码路径 / 函数 / 方法）**

> - `app/bootstrap.py` → `bootstrap_paths()`：stage12 优先；挂 05–10 `src`
> - `app/bridge11.py` → `load_stage11()` / `wire_stage11(app)`：临时路径切换加载 11 routers+deps；对齐 `STAGE11_LOG_DIR` 等 env
> - `app/config.py` → `Stage12Config` + `load_dotenv`；兼容 `STAGE12_*` / `STAGE11_*` / `MED_RAG_*`
> - `app/deps.py` → `get_session_store` / `get_qa_logger` / `get_rag_service` 转调 11 单例
> - `app/main.py` → FastAPI `stage=12-0`；挂 health/qa；OpenAPI 预留 sessions/stats/documents
> - `app/documents_index.py` → `build_documents_index(mode)` 批 upsert + `progress_{mode}.json` / `manifest_{mode}.json`
> - `scripts/build_documents_index.py` → CLI（`--status` / `--resume` / `--batch-size`）
> - `scripts/run_api.py` → uvicorn `app.main:app`
> - `notebooks/api-ops-smoke.ipynb` **C0 / C0.5**
> - `notebooks/api-ops-full.ipynb` **F0**
> - 根 `dataset_paths.py` / `06/.../config.py`（此前已就绪）
> - `.env.example` · `requirements.txt` · `docs/部署与API调用说明.md`（骨架）
> - `tests/test_stage0_skeleton.py`

### 阶段 1：会话管理 API ✅

- [x] 扩展 Store：`delete(session_id)`（+ Protocol）；**不**新建第二套 dict
- [x] `POST /api/v1/sessions` → `store.create` → 返回 `session_id`
- [x] `GET /api/v1/sessions/{session_id}` → `require`；返回 `SessionDetail`（完整 `turns`）；过期/不存在 → **3002**
- [x] `DELETE /api/v1/sessions/{session_id}` → `delete`；不存在仍 **3002**（与 GET 一致）
- [x] 与 `/qa` 联调：同一 `session_id` 两轮后 `turn_count=2`（一轮 = 一条 SessionTurn）
- [x] 文档写清：QA 路径对无效 id **自动新建** ≠ GET/DELETE 的 3002
- [x] 单元测试：create / get / delete；与 mock `/qa` 联调 append；`tests/test_sessions.py`
- [x] Notebook **C1**（`api-ops-smoke.ipynb`）

**阶段 1 完成说明**

> 会话从「带个 session_id」升级为可 **开桌 / 查完整历史 / 撤桌**。  
> `/qa` 仍自动 `append` 一轮 turn，并与 sessions **共用** 11 `MemorySessionStore` 单例。  
> GET 返回完整 `answer`（替代 11 的 `answer_preview` 摘要）；挂载前从 11 `qa_router` 去掉旧 GET，避免 `_IncludedRouter` 抢路由。

**阶段 1 实现说明（代码路径 / 函数 / 方法）**

> - 11 `app/services/session_store.py`：`SessionStore.delete` / `MemorySessionStore.delete` → 缺失/过期抛 `3002`
> - `app/schemas/session.py`：`SessionCreateResponse` / `SessionTurnOut` / `SessionDetail` / `SessionDeleteResponse`
> - `app/services/session_service.py`：`epoch_to_iso` / `record_to_detail`
> - `app/api/sessions.py`：`POST/GET/DELETE /api/v1/sessions…`；`Depends(get_session_store)`
> - `app/bridge11.py`：`wire_stage11(..., drop_session_get=True)` 去掉 11 摘要 GET
> - `app/main.py`：`include_router(sessions_router)`；`stage=12-1`
> - `tests/test_sessions.py`；11 `tests/test_session_store.py` 增补 delete
> - `notebooks/api-ops-smoke.ipynb` **C1**
> - `docs/部署与API调用说明.md` 会话表

### 阶段 2：运营统计 API ✅

- [x] `stats_service`：解析 **与问答相同路径** 的 `qa_calls.jsonl`（允许注入 path 便于单测 fixture）
- [x] `GET /api/v1/stats/qa`：次数 / 平均耗时（ms→秒）/ 成功率
- [x] `GET /api/v1/stats/index`：
  - [x] `chunk_count`：Chroma collection count（随 `retrieval_mode` sample/full）
  - [x] `index_size_bytes`：persist 目录大小
  - [x] `document_count`：当前模式 documents sqlite 的 `COUNT(*)`（sample 或 full；**勿填 chunk 数**）
  - [x] （可选）BM25 片数（full `manifest.num_shards`）
  - [x] `incremental_update_count=0` + `note`
- [x] `GET /api/v1/stats/health`：
  - [x] LLM：复用 `probe_ollama`
  - [x] 向量库：persist 可访问 + count；full 时附 `probe_full_dataset` 子集
  - [x] 数据库：固定 `skipped` + 说明（JSONL 日志非 DB）
  - [x] API：自身 ok
- [x] 单元测试：fixture JSONL 聚合；空文件边界
- [x] Notebook **C2**：fixture JSONL → 展示三个 stats 返回结构

**阶段 2 完成说明**

> 把 11 的 `qa_calls.jsonl` 与 `probe_ollama`「接口化」为三个只读 stats 端点。  
> 无独立 DB → `database=skipped`；`document_count`（篇）与 `chunk_count`（块）严格分开。  
> `/stats/qa` 读与 `/qa` 相同的 logger 路径；单测 / C2 可注入 fixture path。

**阶段 2 实现说明（代码路径 / 函数 / 方法）**

> - `app/schemas/stats.py`：`QAStats` / `IndexStats` / `ComponentHealth` / `HealthStats`
> - `app/services/stats_service.py`
>   - `aggregate_qa_stats(path) -> QAStats`：按行解析 JSONL；`status==ok` 计成功；`latency_ms/1000`→秒；空/缺文件全 0
>   - `collect_index_stats(mode) -> IndexStats`：Chroma count + persist 目录大小 + `documents_index.status` 行数；full 可选 `bm25_num_shards`
>   - `collect_component_health() -> HealthStats`：llm / vector_db / database(skipped) / api
> - `app/api/stats.py`：`GET /api/v1/stats/{qa,index,health}`；`Depends(get_qa_logger)` 共享路径
> - `app/bridge11.py`：缓存导出 `probe_ollama` / `probe_full_dataset`
> - `app/main.py`：`include_router(stats_router)`；`stage=12-2`；`stats=qa+index+health`
> - `tests/test_stats.py`：fixture 聚合 + 空文件 + 三端点
> - `notebooks/api-ops-smoke.ipynb` **C2**
> - `docs/部署与API调用说明.md` 统计表

### 阶段 3：文档管理 API ✅

- [x] `DocumentIn` / 响应模型；**`doc_id` = `pmcid`**
- [x] `DocumentStore`：读 **`DOCUMENTS_SAMPLE_SQLITE`**（开发）/ 可配置 full；按 pmcid 查询与分页
- [x] `GET /api/v1/documents`：分页（`PageModel`）；可选 `q` 标题关键词
- [x] `GET /api/v1/documents/{doc_id}`：命中返回；未命中 **`AppException(3001)`**（非裸 HTTP 404）
- [x] 收紧 11 通用 HTTP 404→3001 映射（路由未命中改用 **1001** + 原样 message，避免污染文档语义）
- [x] 单元测试：列表分页、按 id、不存在 → 3001
- [x] Notebook **C3**：分页列表 → 已知 pmcid → 未知 id 得 `3001`

**阶段 3 完成说明**

> 文献元数据做成**只读菜单册**：sample sqlite 开发默认，full 由 `STAGE12_DOCUMENTS_MODE` 切换。  
> `doc_id` 即 `pmcid`；缺失文档显式抛 **3001**。  
> 11 通用 HTTP 404 不再映射 3001（改 1001），避免「路由不存在」污染「文档不存在」。

**阶段 3 实现说明（代码路径 / 函数 / 方法）**

> - `app/schemas/document.py`：`DocumentIn`（`doc_id`/`title`/`abstract`/`journal`/`pub_date`/`pmid`/`pub_year`）
> - `app/services/document_store.py`：`DocumentStore.get_document` / `list_documents`（只读 sqlite + LIKE 标题）
> - `app/api/documents.py`：`GET /api/v1/documents`（`PageModel`）· `GET /api/v1/documents/{doc_id}` → 缺失 `AppException(DOC_NOT_FOUND)`
> - `app/deps.py`：`get_document_store()`（按 `documents_mode`）
> - `app/bridge11.py`：导出 `AppException` / `ErrorCode` / `PageModel`
> - 11 `app/core/exceptions.py`：HTTP 404 → `PARAM_ERROR(1001)`（不再 `DOC_NOT_FOUND`）
> - `app/main.py`：`include_router(documents_router)`；`stage=12-3`
> - `tests/test_documents.py`；`notebooks/api-ops-smoke.ipynb` **C3**
> - `docs/部署与API调用说明.md` 文档表

### 阶段 4：测试、OpenAPI、部署文档 ✅

> `.env.example` 与基础加载已在阶段 0；本阶段做 **变量清单文档化**、契约补强与集成验收。  
> Notebook **C4**（`api-ops-smoke.ipynb`）= **样本**全链路冒烟。  
> **本阶段结束后**再进入阶段 5 全量仿真（独立 `api-ops-full.ipynb`）。

- [x] 单元测试覆盖新端点；集成测试用 `TestClient` 串会话→问答→统计→文档
- [x] Postman Collection：导入可跑通主要端点（含环境变量）
- [x] OpenAPI：补充 summary/description/example；确认 `/docs`、`/redoc` 可用；tags 分组齐全
- [x] 环境变量：核对 `.env.example` 与加载逻辑；部署文档列出全部变量
- [x] `docs/部署与API调用说明.md`：
  - [x] 本地启动步骤（conda、Ollama、`run_api.py`）
  - [x] curl / httpx 调用示例
  - [x] Postman 使用说明
  - [x] 与 11 差异 / 升级说明
  - [x] 说明：日常 sample；全量见阶段 5 / `api-ops-full.ipynb`
- [x] Notebook **C4**：端到端联调（**sample**；创建会话 → `/qa` → 查历史 → stats → documents）+ `/docs` 分组目视确认

**阶段 4 完成说明**

> 样本路径上验收与对接配套齐：集成测试串通会话→问答→统计→文档；Postman / `/docs` / 部署说明可直接给对接方。  
> C4 证明 12 新 API 与 11 问答能串在一条链上。全量仿真留给阶段 5。

**阶段 4 实现说明（代码路径 / 函数 / 方法）**

> - `tests/test_integration_api.py`：mock `/qa` 全链路 + OpenAPI tags/`/docs`/`/redoc`
> - `postman/MedRAG_API.postman_collection.json`：`baseUrl` / `sessionId` / `docId`
> - `docs/部署与API调用说明.md`：启动、变量表、curl/httpx、Postman、与 11 差异、full 预告
> - OpenAPI：`app/main.py` description + tags；`sessions`/`stats`/`documents` summary/responses
> - `.env.example`：补全注释与变量清单
> - `app/main.py`：`stage=12-4`
> - `notebooks/api-ops-smoke.ipynb` **C4**

### 阶段 5：全量 Dataset 仿真（原 4.5 升级）☐

> **时机**：阶段 4 + smoke C0–C4 完成之后（**`documents/full` 索引已齐**，2026-07-27）。  
> **独立 notebook**：`api-ops-full.ipynb` = **F0 建库（可提前开）** + **F1+ 全量仿真（本阶段）**。  
> **目标**：尽可能模拟打包运行——`retrieval_mode=full`、真 Ollama、会话/统计/问答 + **documents_full**；**不改 API 能力**；**不是** 09 质量复评。  
> 须**重启**进程切 full（禁止每请求换库）。

**先澄清（避免与阶段 2 `document_count` 混淆）**

| 指标 / API | sample（0–4） | full（本阶段 5） | 说明 |
|------------|---------------|------------------|------|
| `chunk_count`（`/stats/index`） | 样本 Chroma ~1,267 | **全量 ~610 万** | 随 `retrieval_mode` 变；**可以、也应该**在阶段 5 打到全量 |
| `document_count` | sample sqlite 行数 | **documents_full 行数（~455 万）** | 与 chunk_count 分开 |
| `/documents` | sample sqlite | **documents_full.sqlite** | 阶段 5 **完整接入全库索引**；qa 的 pmcid 应可 get |
| `/qa` · 会话 · health.vector | sample/mock | **full 真跑** | 本阶段重点 |

→ 阶段 2 的 checklist 写「`document_count`：样本索引条数」= **篇级菜单册字段语义**，不阻碍 `/stats` 在 full 下报告全量 `chunk_count`。

**本阶段在验什么（尽可能贴近实战）**

| 链路 | 期望 |
|------|------|
| 资源自检 | `chroma_db_full` + `bm25_full` + **`documents_full.sqlite`（已 completed）** + Ollama |
| `/stats/index` | `chunk_count`≈全量；`index_size_bytes` 合理；`document_count` 不与 chunk 混用 |
| `/stats/health` | llm/vector/api 明确；database=`skipped` |
| `/stats/qa` | 本阶段 live 调用后计数增加 |
| 会话 CRUD + `/qa` | 显式创建会话 → 同 id **两轮** live；`turn_count=2`；sources 为**全量 pmcid** |
| （建议）`/qa/stream` | 伪 SSE 一轮可完成 |
| `/documents` | **走 documents_full**：list 分页；对 `/qa` 返回 pmcid **get 应 200** |
| 耗时 / 日志 | 记录墙钟；专用 JSONL（如 `qa_calls_full_ops.jsonl`），避免与开发 sample 日志混淆 |

- [ ] `api-ops-full.ipynb` **F0**（若阶段 0 未做完）：建库 / `--status` / 进度可视化；确认 `manifest.status=completed`
- [ ] 同本 **F1+**：就绪自检 → 切 full/预热 → stats → sessions+qa 两轮 → stream → documents 对照 → 汇总导出
- [ ] CLI `scripts/run_full_ops_smoke.py`（可被 notebook 调用或独立长跑）
- [ ] 资源自检：复用/扩展 11 `probe_full_dataset` + documents_full manifest
- [ ] 进程 `retrieval_mode=full`；预热 pipeline（Windows 路径/线程池坑 → 优先主线程，对齐 11）
- [ ] `GET /stats/index|health|qa` 全量口径验收
- [ ] 会话 + `POST /qa` **至少 1–2 条**熟悉 query + 同 session 第二轮
- [ ] （建议）伪 SSE 一轮；确认 `/stats/qa` 计入
- [ ] documents：**documents_full** list + qa pmcid get=200
- [ ] 导出 `outputs/reports/full_ops_smoke*`（JSON / 可选图）
- [ ] 部署文档补充「如何切换 full / 跑 api-ops-full（含 F0 建库）」

**阶段 5 完成说明**

> （预留）大白话：用全库 + 真模型把 12 的会话/统计/问答（及文档对照）按接近上线的方式跑通；样本契约仍由 smoke 负责；full 本负责建库观察（F0）+ 生产路径仿真（F1+）。

**阶段 5 实现说明（代码路径 / 函数 / 方法）**

> （预留）
>
> - `notebooks/api-ops-full.ipynb` **F0 / F1+** → …
> - `scripts/build_documents_index.py --mode full`（F0 调用）→ …
> - `scripts/run_full_ops_smoke.py` → …
> - （可选）`app/full_ops_smoke.py` → …
> - 产物：`outputs/reports/full_ops_smoke*` → …

### 阶段 6：交付收尾 ☐

> 样本演示在 `api-ops-smoke`（C0–C4）；全量仿真在 `api-ops-full`（阶段 5）。本阶段做**打包与文档对齐**。

- [ ] 复核 smoke C0–C4 与 `api-ops-full` 与代码一致；必要时重跑保存输出
- [ ] 导出一份 stats 样例到 `outputs/samples/`（可选）
- [ ] 更新根目录 `README.md` 阶段 12 条目；确认 Dataset README 已含样本复制/重建说明
- [ ] （可选）正式报告 `docs/服务化接口第二部分报告.md`（引用阶段 5 全量素材）

**阶段 6 完成说明**

> （预留）交付包对齐：README ✅、可选报告、样例输出、双 notebook 复核。

**阶段 6 实现说明（代码路径 / 函数 / 方法）**

> （预留）
>
> - 根目录 `README.md` 阶段 12 条目 → …
> - `docs/服务化接口第二部分报告.md`（若写）→ …
> - `outputs/samples/`（若导出）→ …
> - `api-ops-smoke.ipynb` + `api-ops-full.ipynb` 运行记录复核 → …

---

## 验证用例（首批）

| # | 场景 | 期望 |
|---|------|------|
| 1 | 创建会话 → 同 session_id 调 /qa 两轮（可 mock） | 	urn_count=2；每 turn 含 query+nswer（**不是** 4 条 role 消息） |
| 2 | GET 该会话 | 返回完整 	urns 历史 |
| 3 | DELETE 后再 GET | **3002** |
| 3b | /qa 带已删除/过期 session_id | **自动新建**并返回新 id（与 11 一致；≠ 3002） |
| 4 | /stats/qa（fixture 或实跑后） | 	otal_calls 增加；成功率 ∈ [0,1]；耗时单位正确 |
| 5 | /stats/index（sample） | chunk_count/index_size_bytes 有值；document_count 不与 chunk 混淆 |
| 5b | /stats/index（full · **阶段 5**） | chunk_count 为全量量级（约 610 万） |
| 6 | /stats/health | llm/vector/api 有明确 status；**database=skipped** |
| 7 | /documents 分页 | PageModel；sample 或 full sqlite（随模式） |
| 8 | /documents/{unknown} | **3001**（业务码，非「路由不存在」误伤） |
| 9 | Postman / TestClient 全端点冒烟 | 全绿（sample · pi-ops-smoke） |
| 10 | /docs | Swagger 含 sessions/stats/documents 分组 |
| 11 | **阶段 5** api-ops-full：full + Ollama 会话两轮 /qa | 200/code=0；sources 为全量 pmcid；报告素材落盘 |

---

## 交付产物清单（预填）

| 产物 | 格式 | 路径 | Git |
|------|------|------|-----|
| 会话 / 统计 / 文档 API | Python | app/api/*.py（+ 必要时扩展 11 Store） | ✅ |
| DocumentIn 等模型 | Python | app/schemas/ | ✅ |
| 文档索引 sample/full | sqlite | **Dataset/documents/{sample,full}/** | ❌（README 写重建） |
| 样本 chunks（从 03 **复制**） | JSONL | **Dataset/processed/chunks_sample.jsonl** | ❌（README 写来源） |
| dataset_paths 扩展 | Python | 根 dataset_paths.py | ✅ |
| .env.example | env | .env.example | ✅ |
| Postman 集合 | JSON | postman/MedRAG_API.postman_collection.json | ✅ |
| 部署与调用说明 | Markdown | docs/部署与API调用说明.md | ✅ |
| 单元/集成测试 | Python | tests/ | ✅ |
| 样本 smoke notebook（C0–C4；C0.5 建 sample 索引） | .ipynb | notebooks/api-ops-smoke.ipynb | ✅ |
| 全量 notebook（F0 建库可视化 + 阶段 5 仿真） | .ipynb | notebooks/api-ops-full.ipynb | ✅ |
| 全量抽检素材 | JSON/图 | outputs/reports/full_ops_smoke* | ✅（小文件） |
| OpenAPI | 自动 | /docs | — |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 12 与 11 **两套 SessionStore / 两套 log_dir** | 会话 CRUD 与 /qa 互不可见；stats 恒空 | **强制共用** 11 deps 单例与同一 log_dir；阶段 0 验收 |
| 按 role 消息验收（4 条）vs 实际 turn（2 条） | 联调「失败」假象 | **定稿方案 A**：对外 turns；验证用例写 	urn_count=2 |
| 把 Chroma count 写成「文档总数」 | 统计语义错误（610 万 chunks ≠ 455 万篇） | 分开 chunk_count / document_count |
| 误以为「阶段 2 只有样本索引 → 阶段 5 无法 full」 | 不敢切 full，或误去扫 slim | 见阶段 5 澄清表：chunk_count 可 full；菜单册是另一条线（笔记 Q6） |
| 样本仍散落 03/04，新代码继续硬编码阶段路径 | 管理混乱；动旧目录易破坏既往阶段 | **只复制**进 Dataset；旧目录只读不动；新代码走 dataset_paths |
| 误 move/改联接旧阶段文件 | 03/04 notebook 或评测路径断裂 | checklist 明确 **copy only**；禁止删改来源 |
| 以为小样本要进 Git | 与 Dataset ignore 策略冲突、PR 噪音 | **不进 Git**；重建说明写在 Dataset/README.md |
| 全量 slim 列表太慢/太大 | 文档 API 不可用 | MVP 样本 JSON；阶段 5 **不**扫全库做 documents 列表 |
| 「增量更新次数」无数据源 | 字段空或造假 | MVP 返回 0 + note |
| 无独立数据库 | health 难对齐任务书字面 | 明确 database=skipped |
| 通用 HTTP 404→**3001** | 任意错路径都像「文档不存在」 | 上文档 API 时收紧 handler |
| 只在 sample 验收、接 full 才暴露路径/体积/耗时问题 | 后续产品化踩坑 | **阶段 5** + api-ops-full.ipynb 全量仿真 |
| 把全量章节塞进 smoke 导致本又慢又难维护 | 日常 C0–C4 不敢跑 | **双 notebook**：smoke=样本；full=F0 建库+阶段 5 仿真 |
| 等 full 建完才敢写 1–4 | 墙钟空转 | **C0.5 sample 就绪即可进 1–4**；full 后台/F0 并行 |
| 最小改 11 结案代码 vs 完全 fork | 维护成本 | 优先：11 仅加 delete；12 加 router；结案 README 写清**启动目录以 12 为准** |
| Postman 依赖本机服务 | CI 难跑 | pytest TestClient 主验收；Postman 人工集成 |

---

## 本周执行顺序（建议）

> 每完成一小阶段：**勾选 checklist → 填写完成/实现说明 → 补齐对应 notebook → 再进下一阶段**。

1. **阶段 0** ✅ 骨架 + sample 索引 + **full 索引已落盘**  
2. **阶段 1–4** 用 **sample** 写会话/统计/文档/测试 + smoke C1–C4  
3. **阶段 5** `api-ops-full` F1+ 全量仿真（检索 full + **已有** documents_full + Ollama）  
4. **阶段 6** 交付收尾

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-07-27 | 创建阶段 12 schedule.md，对齐任务书与 11 已交付 API，待启动实施 |
| 2026-07-27 | **计划修订（习惯层）**：notebook 改为贯穿式 C0–C4（对齐 09/11）；原「阶段 5=Notebook 联调与交付」改为「交付收尾」；各小阶段预留完成说明 / 实现说明；.env.example 归阶段 0，阶段 4 做变量文档化与集成验收 |
| 2026-07-27 | **计划修订（内容层）**：对照 11 源码定稿——共用 SessionStore/log 单例；补 delete；会话对外 turns 非 role 双条；stats 区分 chunk/文档；doc_id=pmcid；收紧 3001；砍会话列表与公开 messages；验证用例对齐 QA 自动新建 vs GET 3002 |
| 2026-07-27 | **计划修订（样本统一 + 4.5）**：样本 **复制**进 Dataset（不改 03/04）；**不进 Git**，README 写来源/重建；曾设阶段 4.5 全量抽检 |
| 2026-07-27 | **样本策略确认**：明确 copy-only、不影响既往阶段、无 gitignore 例外 |
| 2026-07-27 | **计划修订（全量升格）**：原 4.5 → **阶段 5**；新建 **api-ops-full.ipynb**；原交付 → **阶段 6**；澄清 document_count≠阻碍 full chunk_count |
| 2026-07-27 | **定稿做全库文档索引**：`Dataset/documents`；阶段 0 建 sample+full；阶段 5 完整接入；打包/补丁计划见（打包）02schedule 与（未来优化） |
| 2026-07-27 | **资产**：`chunks_sample.jsonl` 已复制进 Dataset；更新 `dataset_paths` / Dataset README / 缓存记录 / 根 README |
| 2026-07-27 | **建库节奏**：smoke C0.5=样本索引（进 1–4 门槛）；api-ops-full **F0**=全量建库可视化（可与 1–4 并行/后台）；阶段 5 等 full completed 再仿真 |
| 2026-07-27 | **阶段 0 实施完成**：骨架+bridge11；documents_sample 1000 篇；smoke C0/C0.5；full F0 入口就绪 |
| 2026-07-27 | documents 改为 `sample/` 与 `full/` 分目录；smoke C0.5 默认不重建；F0 对准新路径 |
| 2026-07-27 | **F0 全量文档索引完成**：`documents/full` · 4,557,627 篇 · manifest completed · 逻辑分片单库（非物理多 shard） |
| 2026-07-28 | **阶段 1 实施完成**：sessions CRUD + Store.delete；smoke C1；与 /qa 同单例 |
