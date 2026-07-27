# 12 服务化与接口开发第二部分 — 执行计划

> **状态：🔄 待启动**
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
| 索引统计 | `chunk_count`←Chroma `count`；`index_size_bytes`←persist 目录；BM25 片数可选 | **`document_count`≠ chunk 数**：篇级可用样本索引条数或标 `null`+note；「增量更新次数」MVP=`0`+note |
| 文档列表数据源 | **MVP：`Dataset/documents/documents_sample.json`**（由 slim/样本 pmcid 预抽）；`doc_id`**=`pmcid`** | 全量 slim 不宜每次全扫；12 可留生成脚本，**权威路径在 Dataset** |
| 样本资产落点 | **复制**进 `Dataset/`（**不改动** 03/04 原文件）；新代码读 Dataset | 见下节；**不进 Git**，仅在 Dataset README 写清来源与重建步骤 |
| `3001` 语义 | 文档按 id 未命中 → `AppException(DOC_NOT_FOUND)` | 修复/绕开 11「任意 HTTP 404→3001」映射，避免路由未命中冒充「文档不存在」 |
| 认证 | 继续预留 `2001`，本周不做真实鉴权 | 与 11 一致 |
| 本阶段边界 | **不做** 前端 UI、真实增量入库写接口、生产 K8s、会话列表 API、全量文档目录扫描 | 文档只读查询；全量连通见 **4.5** |

### 样本资产复制进 Dataset（本周一并做）

> **原则（定稿）**  
> 1. **只复制、不移动、不改联接**——03/04 等历史阶段目录原样保留，避免影响既往 notebook/脚本。  
> 2. **不进 Git**——继续遵循 `/Dataset/**` ignore（仅提交 `Dataset/README.md`）。  
> 3. **README 可重建**——在 `Dataset/README.md` 写明「从哪复制、命令/步骤、生成 documents 索引的脚本」，克隆后按说明本地重建即可。  
> 4. 12 与后续开发 **优先读 Dataset**（`dataset_paths.py`）；旧阶段路径仅作历史兼容回退。

> **现状澄清**：`Dataset/` **已有**样本向量库 `chroma/chroma_db`（1,267）与全量资产；**尚未收拢副本**的是 **`chunks_sample.jsonl`**（仍在 `03`/`04`），以及 12 新建的 **`documents_sample.json`**。

| 资产 | 复制来源（只读，勿删） | Dataset 目标路径 | Git |
|------|------------------------|------------------|-----|
| 样本 Chroma | （已在 Dataset；来源曾为 04） | `chroma/chroma_db/` | ❌ ignore |
| `chunks_sample.jsonl`（~1.9 MB） | **`03 .../data/processed/chunks_sample.jsonl`**（04 为同内容副本，任选其一复制） | **`processed/chunks_sample.jsonl`** | ❌ ignore；README 写来源 |
| `documents_sample.json`（新建） | 由脚本从 `chunks_sample` pmcid + `oa_comm_slim.jsonl`（或 02 样本字段）**生成**，非直接复制单文件 | **`documents/documents_sample.json`** | ❌ ignore；README 写生成命令 |
| 全量资产 | 已在 Dataset | 不变 | ❌ ignore |

**实施要点（阶段 0）**

1. `copy`（非 move）`chunks_sample.jsonl` → `Dataset/processed/`；**禁止**删除或改写 03/04 原文件。  
2. 扩展根目录 [`dataset_paths.py`](../dataset_paths.py)：`CHUNKS_SAMPLE_JSONL`、`DOCUMENTS_SAMPLE_JSON`。  
3. 更新 `06/src/config.py` 的 `resolve_chunks_path("sample")`：**优先 Dataset 副本**，找不到再回退 03/04（旧阶段零感知）。  
4. `scripts/build_documents_sample.py` 生成 `Dataset/documents/documents_sample.json`（DocumentStore 只读此路径）。  
5. **只改** [`Dataset/README.md`](../Dataset/README.md)：布局 +「样本重建」小节（来源路径、复制命令、生成脚本）；**不**为小文件开 gitignore 例外。  
6. 12 的 DocumentStore / 新代码 **只读 Dataset**；不要把权威副本只放在 `12/data/`。


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

### DocumentIn ↔ slim 字段映射

| `DocumentIn` | slim / 样本来源 | 备注 |
|--------------|-----------------|------|
| `doc_id` | `pmcid` | 主键；路径参数即 pmcid |
| `title` | `title` | |
| `abstract` | `abstract` | 列表接口可截断 |
| `journal` | `journal` | 未标准化 |
| `pub_date` | `pub_date`（缺则可用 `pub_year`） | |

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
│   ├── api-ops-smoke.ipynb          # 样本主轨：C0/C0.5 → C1…C4
│   └── api-ops-full.ipynb           # 阶段 5：全量仿真（独立本，不塞进 smoke）
├── scripts/
│   ├── run_api.py
│   ├── build_documents_sample.py    # 从 Dataset slim/chunks_sample 生成 documents 索引
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
> - **样本主轨**：单一 notebook `notebooks/api-ops-smoke.ipynb`（**C0 → C4**）贯穿阶段 0–4。  
> - **全量专轨**：阶段 4 完成后再开 **阶段 5**，使用独立 notebook **`notebooks/api-ops-full.ipynb`**，尽可能模拟未来生产（full Dataset + Ollama）。  
> - **阶段 6** = 交付收尾（README / 可选报告 / 复核）。  
> 每完成一小阶段：**勾选 checklist → 填写完成说明 / 实现说明 → 补齐对应 notebook → 再进下一阶段**。

```text
0 骨架+.env+样本复制 → C0/C0.5（api-ops-smoke）
1 会话 → C1 · 2 统计 → C2 · 3 文档 → C3 · 4 测试/文档 → C4
5 全量仿真（api-ops-full.ipynb）← 原 4.5 升级为独立阶段
6 交付收尾
```

### 阶段 0：环境与骨架 + 样本复制进 Dataset ☐

- [ ] 创建目录结构（`app/`、`scripts/`、`tests/`、`notebooks/`、`outputs/`、`postman/`、`docs/`）
- [ ] `requirements.txt`（复用 11 + `python-dotenv` 如需）
- [ ] `.env.example`（兼容 11：`MED_RAG_RETRIEVAL_MODE`、`STAGE11_HOST`/`PORT`/`LOG_DIR`/`SESSION_*` 等；可加 `STAGE12_*` 别名）+ dotenv 加载
- [ ] `bootstrap`：挂 11 目录使 `import app` 指向 **11 的 app 包**（或明确包别名策略）；注意与上游 `src/config` 撞名
- [ ] `main.py`：创建 FastAPI；**include 11 的 health/qa router**；预留 sessions/stats/documents tags
- [ ] **单例策略写清**：`get_session_store` / `get_qa_logger` / `get_rag_service` 必须与 `/qa` 同一进程实例
- [ ] **样本复制进 Dataset**（**不改动** 03/04 原文件；不进 Git）：
  - [ ] `copy`：`03 .../chunks_sample.jsonl` → `Dataset/processed/chunks_sample.jsonl`
  - [ ] 扩展 `dataset_paths.py`：`CHUNKS_SAMPLE_JSONL`、`DOCUMENTS_SAMPLE_JSON`
  - [ ] `06 resolve_chunks_path("sample")` 优先 Dataset（回退仍指向未改动的 03/04）
  - [ ] 脚本生成 `Dataset/documents/documents_sample.json`（可先占位，阶段 3 填全）
  - [ ] 更新 `Dataset/README.md`：**复制来源 + 重建步骤**（无 gitignore 例外）
- [ ] `scripts/run_api.py` 可启动
- [ ] Notebook **C0**：环境初始化、目录与依赖自检、`TestClient` 打 `/` 或 `/health`
- [ ] Notebook **C0.5**：确认 Dataset 样本路径可读；可 import 11 `ResponseModel` / `MemorySessionStore` / `RagService` / `QACallLogger`

**阶段 0 完成说明**

> （预留）搭好 12 工程骨架；bootstrap 挂 11；**将样本 chunks / documents 索引复制进 Dataset（旧阶段不动）**；`Dataset/README` 写明来源与重建；贯穿式 notebook 建好 C0 / C0.5。本阶段尚无会话 CRUD / 统计 / 文档业务 API。

**阶段 0 实现说明（代码路径 / 函数 / 方法）**

> （预留 · 完成后按 09/11 写法回填：路径 / 函数 / 思路·输入·输出）
>
> - `app/bootstrap.py` → …
> - `app/config.py` → …
> - `app/main.py` → …
> - 根 `dataset_paths.py` 新增常量 → …
> - `06/.../config.py`：`resolve_chunks_path` 优先 Dataset → …
> - `scripts/build_documents_sample.py` → …
> - `Dataset/README.md`（来源与重建说明；**无** gitignore 例外）→ …
> - `.env.example` → …
> - `scripts/run_api.py` → …
> - `notebooks/api-ops-smoke.ipynb` **C0 / C0.5** → …

### 阶段 1：会话管理 API ☐

- [ ] 扩展 Store：`delete(session_id)`（+ Protocol）；**不**新建第二套 dict
- [ ] `POST /api/v1/sessions` → `store.create` → 返回 `session_id`
- [ ] `GET /api/v1/sessions/{session_id}` → `require`；返回 `SessionDetail`（完整 `turns`，可替代/增强 11 摘要版）；过期/不存在 → **3002**
- [ ] `DELETE /api/v1/sessions/{session_id}` → `delete`；幂等策略写清（推荐：不存在仍 **3002**，与 GET 一致）
- [ ] 与 `/qa` 联调：同一 `session_id` 两轮后 `turn_count=2`（**一轮 = 一条 SessionTurn**，非 user/assistant 各一条）
- [ ] 文档写清：QA 路径对无效 id **自动新建** ≠ GET/DELETE 的 3002
- [ ] 单元测试：create / get / delete / TTL；与 mock `/qa` 联调 append
- [ ] Notebook **C1**：创建会话 →（mock）`/qa` 两轮 → GET 见 2 turns → DELETE → 再 GET 见 `3002`

**阶段 1 完成说明**

> （预留）通俗说明：会话从「带个 session_id」升级为可 **开桌 / 查历史 / 撤桌**；`/qa` 自动 `append` 一轮 turn；多轮上下文延续 11 MVP（Store + query 前缀）。

**阶段 1 实现说明（代码路径 / 函数 / 方法）**

> （预留）
>
> - 11 `session_store.py`：`MemorySessionStore.delete` / Protocol 扩展 → …
> - `app/api/sessions.py`（或 12 路由包装 11 store）→ …
> - `app/schemas/session.py`：`SessionDetail` / `SessionTurnOut` → …
> - 与 `/qa` 共用 `deps.get_session_store()` → …
> - `tests/test_sessions.py` → …
> - `notebooks/api-ops-smoke.ipynb` **C1** → …

### 阶段 2：运营统计 API ☐

- [ ] `stats_service`：解析 **与问答相同路径** 的 `qa_calls.jsonl`（允许注入 path 便于单测 fixture）
- [ ] `GET /api/v1/stats/qa`：次数 / 平均耗时（ms→秒）/ 成功率
- [ ] `GET /api/v1/stats/index`：
  - [ ] `chunk_count`：Chroma collection count（随 `retrieval_mode` sample/full）
  - [ ] `index_size_bytes`：persist 目录大小
  - [ ] `document_count`：样本菜单册条数或 `null`+note（**勿填 chunk 数**；与能否 `retrieval_mode=full` 无关，见阶段 5 澄清 / 笔记 Q6）
  - [ ] （可选）BM25 片数
  - [ ] `incremental_update_count=0` + `note`
- [ ] `GET /api/v1/stats/health`：
  - [ ] LLM：复用 `probe_ollama`
  - [ ] 向量库：persist 可访问 + count / `probe_full_dataset` 轻量子集
  - [ ] 数据库：固定 `skipped` + 说明（JSONL 日志非 DB）
  - [ ] API：自身 ok
- [ ] 单元测试：fixture JSONL 聚合；空文件边界
- [ ] Notebook **C2**：fixture 或实写若干 JSONL → 展示三个 stats 返回结构

**阶段 2 完成说明**

> （预留）通俗说明：把 11 的调用流水与探针「接口化」；无独立 DB 时健康项明确 `skipped`；索引指标区分 chunk vs 文档篇数。

**阶段 2 实现说明（代码路径 / 函数 / 方法）**

> （预留）
>
> - `app/api/stats.py` → …
> - `app/schemas/stats.py` → …
> - `app/services/stats_service.py`
>   - `aggregate_qa_stats(path) -> QAStats`：思路 / 输入 / 输出 …
>   - `collect_index_stats(mode) -> IndexStats` → …
>   - `collect_component_health() -> list[ComponentHealth]` → …
> - 复用 11 `probe_ollama` /（可选）`probe_full_dataset` → …
> - `tests/test_stats.py` → …
> - `notebooks/api-ops-smoke.ipynb` **C2** → …

### 阶段 3：文档管理 API ☐

- [ ] `DocumentIn` / 响应模型；**`doc_id` = `pmcid`**
- [ ] `DocumentStore`：加载 **`Dataset/documents/documents_sample.json`**（`dataset_paths.DOCUMENTS_SAMPLE_JSON`）；内存 dict 按 id 索引
- [ ] `GET /api/v1/documents`：分页（`PageModel`）；可选 `q` 标题关键词
- [ ] `GET /api/v1/documents/{doc_id}`：命中返回；未命中 **`AppException(3001)`**（非裸 HTTP 404）
- [ ] 收紧 11 通用 HTTP 404→3001 映射（路由未命中改用中性码或原样 message，避免污染文档语义）
- [ ] 单元测试：列表分页、按 id、不存在 → 3001
- [ ] Notebook **C3**：分页列表 → 已知 pmcid → 未知 id 得 `3001`

**阶段 3 完成说明**

> （预留）通俗说明：文献元数据**只读菜单册**；MVP 样本索引；`3001` 真正用于「文档不存在」。

**阶段 3 实现说明（代码路径 / 函数 / 方法）**

> （预留）
>
> - `app/api/documents.py` → …
> - `app/schemas/document.py` → …
> - `app/services/document_store.py`
>   - `list_documents(page, page_size, q=None)` → …
>   - `get_document(doc_id)` → …
> - `data/documents_sample.json` → …  **改为** `Dataset/documents/documents_sample.json` + `dataset_paths`
> - 异常 handler 修订（11 或 12 覆盖）→ …
> - `tests/test_documents.py` → …
> - `notebooks/api-ops-smoke.ipynb` **C3** → …

### 阶段 4：测试、OpenAPI、部署文档 ☐

> `.env.example` 与基础加载已在阶段 0；本阶段做 **变量清单文档化**、契约补强与集成验收。  
> Notebook **C4**（`api-ops-smoke.ipynb`）= **样本**全链路冒烟。  
> **本阶段结束后**再进入阶段 5 全量仿真（独立 `api-ops-full.ipynb`）。

- [ ] 单元测试覆盖新端点；集成测试用 `TestClient` 串会话→问答→统计→文档
- [ ] Postman Collection：导入可跑通主要端点（含环境变量）
- [ ] OpenAPI：补充 summary/description/example；确认 `/docs`、`/redoc` 可用；tags 分组齐全
- [ ] 环境变量：核对 `.env.example` 与加载逻辑；部署文档列出全部变量
- [ ] `docs/部署与API调用说明.md`：
  - [ ] 本地启动步骤（conda、Ollama、`run_api.py`）
  - [ ] curl / httpx 调用示例
  - [ ] Postman 使用说明
  - [ ] 与 11 差异 / 升级说明
  - [ ] 说明：日常 sample；全量见阶段 5 / `api-ops-full.ipynb`
- [ ] Notebook **C4**：端到端联调（**sample**；创建会话 → `/qa` → 查历史 → stats → documents）+ `/docs` 分组目视确认

**阶段 4 完成说明**

> （预留）通俗说明：样本路径上验收与对接配套齐；C4 证明新 API 与 11 问答能串在一条链上。全量仿真留给阶段 5。

**阶段 4 实现说明（代码路径 / 函数 / 方法）**

> （预留）
>
> - `tests/test_integration_api.py` → …
> - `postman/MedRAG_API.postman_collection.json` → …
> - `docs/部署与API调用说明.md` → …
> - OpenAPI 注解落点 → …
> - `notebooks/api-ops-smoke.ipynb` **C4** → …

### 阶段 5：全量 Dataset 仿真（原 4.5 升级）☐

> **时机**：阶段 4 + `api-ops-smoke.ipynb`（C0–C4）完成之后。  
> **独立 notebook**：`notebooks/api-ops-full.ipynb`（**不要**再把全量章节塞进 smoke）。  
> **目标**：尽可能模拟未来实际使用——进程 `MED_RAG_RETRIEVAL_MODE=full`、真 Ollama、真实会话/统计/问答链路；**不改 API 能力**；**不是** 09 质量复评。  
> 须**重启**进程切 full（禁止每请求换库）。

**先澄清（避免与阶段 2 `document_count` 混淆）**

| 指标 / API | sample（0–4） | full（本阶段 5） | 说明 |
|------------|---------------|------------------|------|
| `chunk_count`（`/stats/index`） | 样本 Chroma ~1,267 | **全量 ~610 万** | 随 `retrieval_mode` 变；**可以、也应该**在阶段 5 打到全量 |
| `document_count`（`/stats/index`） | ≈ `documents_sample.json` 条数 | **仍可为样本菜单册条数**（或 null+note） | 来自 **阶段 3 DocumentStore 预建索引**，不是「阶段 2 只建了样本所以 5 用不了全量 chunk」 |
| `/documents` 列表 | 样本菜单册 | **默认仍样本菜单册** | 未建全库篇级目录索引（见笔记 Q5/Q6）；与 chunk 全量是两条线 |
| `/qa` · 会话 · health.vector | sample/mock | **full 真跑** | 本阶段重点 |

→ 阶段 2 的 checklist 写「`document_count`：样本索引条数」= **篇级菜单册字段语义**，不阻碍 `/stats` 在 full 下报告全量 `chunk_count`。

**本阶段在验什么（尽可能贴近实战）**

| 链路 | 期望 |
|------|------|
| 资源自检 | `chroma_db_full` + `bm25_full` manifest + Ollama +（建议）slim/chunks 存在 |
| `/stats/index` | `chunk_count`≈全量；`index_size_bytes` 合理；`document_count` 不与 chunk 混用 |
| `/stats/health` | llm/vector/api 明确；database=`skipped` |
| `/stats/qa` | 本阶段 live 调用后计数增加 |
| 会话 CRUD + `/qa` | 显式创建会话 → 同 id **两轮** live；`turn_count=2`；sources 为**全量 pmcid** |
| （建议）`/qa/stream` | 伪 SSE 一轮可完成 |
| `/documents` | 样本列表仍可用；**对 `/qa` 返回 pmcid**：样本索引命中则 get 200，否则 3001 + 可选 slim 旁路校验（笔记 Q5 选项 B） |
| 耗时 / 日志 | 记录墙钟；专用 JSONL（如 `qa_calls_full_ops.jsonl`），避免与开发 sample 日志混淆 |

- [ ] 新建 `notebooks/api-ops-full.ipynb`（章节建议：就绪自检 → 切 full/预热 → stats → sessions+qa 两轮 → stream → documents 对照 → 汇总导出）
- [ ] CLI `scripts/run_full_ops_smoke.py`（可被 notebook 调用或独立长跑）
- [ ] 资源自检：复用/扩展 11 `probe_full_dataset`
- [ ] 进程 `retrieval_mode=full`；预热 pipeline（Windows 路径/线程池坑 → 优先主线程，对齐 11）
- [ ] `GET /stats/index|health|qa` 全量口径验收
- [ ] 会话 + `POST /qa` **至少 1–2 条**熟悉 query + 同 session 第二轮
- [ ] （建议）伪 SSE 一轮；确认 `/stats/qa` 计入
- [ ] documents：样本 list；qa pmcid 的 get / 可选 slim 校验 + note
- [ ] 导出 `outputs/reports/full_ops_smoke*`（JSON / 可选图）
- [ ] 部署文档补充「如何切换 full / 跑 api-ops-full」

**阶段 5 完成说明**

> （预留）大白话：用全库 + 真模型把 12 的会话/统计/问答（及文档对照）按接近上线的方式跑通；样本契约仍由 smoke 负责，全量专本负责生产路径。

**阶段 5 实现说明（代码路径 / 函数 / 方法）**

> （预留）
>
> - `notebooks/api-ops-full.ipynb` → …
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
| 1 | 创建会话 → 同 session_id 调 /qa 两轮（可 mock） | 	urn_count=2；每 turn 含 query+nswer（**不是** 4 条 role 消息） |
| 2 | GET 该会话 | 返回完整 	urns 历史 |
| 3 | DELETE 后再 GET | **3002** |
| 3b | /qa 带已删除/过期 session_id | **自动新建**并返回新 id（与 11 一致；≠ 3002） |
| 4 | /stats/qa（fixture 或实跑后） | 	otal_calls 增加；成功率 ∈ [0,1]；耗时单位正确 |
| 5 | /stats/index（sample） | chunk_count/index_size_bytes 有值；document_count 不与 chunk 混淆 |
| 5b | /stats/index（full · **阶段 5**） | chunk_count 为全量量级（约 610 万） |
| 6 | /stats/health | llm/vector/api 有明确 status；**database=skipped** |
| 7 | /documents 分页 | PageModel；数据来自 **Dataset** documents_sample.json |
| 8 | /documents/{unknown} | **3001**（业务码，非「路由不存在」误伤） |
| 9 | Postman / TestClient 全端点冒烟 | 全绿（sample · pi-ops-smoke） |
| 10 | /docs | Swagger 含 sessions/stats/documents 分组 |
| 11 | **阶段 5** pi-ops-full：full + Ollama 会话两轮 /qa | 200/code=0；sources 为全量 pmcid；报告素材落盘 |

---

## 交付产物清单（预填）

| 产物 | 格式 | 路径 | Git |
|------|------|------|-----|
| 会话 / 统计 / 文档 API | Python | pp/api/*.py（+ 必要时扩展 11 Store） | ✅ |
| DocumentIn 等模型 | Python | pp/schemas/ | ✅ |
| 文档样本索引（本地生成） | JSON | **Dataset/documents/documents_sample.json** | ❌（README 写重建） |
| 样本 chunks（从 03 **复制**） | JSONL | **Dataset/processed/chunks_sample.jsonl** | ❌（README 写来源） |
| dataset_paths 扩展 | Python | 根 dataset_paths.py | ✅ |
| .env.example | env | .env.example | ✅ |
| Postman 集合 | JSON | postman/MedRAG_API.postman_collection.json | ✅ |
| 部署与调用说明 | Markdown | docs/部署与API调用说明.md | ✅ |
| 单元/集成测试 | Python | 	ests/ | ✅ |
| 样本 smoke notebook（C0–C4） | .ipynb | 
otebooks/api-ops-smoke.ipynb | ✅ |
| **全量仿真 notebook** | .ipynb | **
otebooks/api-ops-full.ipynb** | ✅ |
| 全量抽检素材 | JSON/图 | outputs/reports/full_ops_smoke* | ✅（小文件） |
| OpenAPI | 自动 | /docs | — |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 12 与 11 **两套 SessionStore / 两套 log_dir** | 会话 CRUD 与 /qa 互不可见；stats 恒空 | **强制共用** 11 deps 单例与同一 log_dir；阶段 0 验收 |
| 按 role 消息验收（4 条）vs 实际 turn（2 条） | 联调「失败」假象 | **定稿方案 A**：对外 	urns；验证用例写 	urn_count=2 |
| 把 Chroma count 写成「文档总数」 | 统计语义错误（610 万 chunks ≠ 455 万篇） | 分开 chunk_count / document_count |
| 误以为「阶段 2 只有样本索引 → 阶段 5 无法 full」 | 不敢切 full，或误去扫 slim | 见阶段 5 澄清表：chunk_count 可 full；菜单册是另一条线（笔记 Q6） |
| 样本仍散落 03/04，新代码继续硬编码阶段路径 | 管理混乱；动旧目录易破坏既往阶段 | **只复制**进 Dataset；旧目录只读不动；新代码走 dataset_paths |
| 误 move/改联接旧阶段文件 | 03/04 notebook 或评测路径断裂 | checklist 明确 **copy only**；禁止删改来源 |
| 以为小样本要进 Git | 与 Dataset ignore 策略冲突、PR 噪音 | **不进 Git**；重建说明写在 Dataset/README.md |
| 全量 slim 列表太慢/太大 | 文档 API 不可用 | MVP 样本 JSON；阶段 5 **不**扫全库做 documents 列表 |
| 「增量更新次数」无数据源 | 字段空或造假 | MVP 返回 0 + 
ote |
| 无独立数据库 | health 难对齐任务书字面 | 明确 database=skipped |
| 通用 HTTP 404→**3001** | 任意错路径都像「文档不存在」 | 上文档 API 时收紧 handler |
| 只在 sample 验收、接 full 才暴露路径/体积/耗时问题 | 后续产品化踩坑 | **阶段 5** + pi-ops-full.ipynb 全量仿真 |
| 把全量章节塞进 smoke 导致本又慢又难维护 | 日常 C0–C4 不敢跑 | **双 notebook**：smoke=样本；full=阶段 5 |
| 最小改 11 结案代码 vs 完全 fork | 维护成本 | 优先：11 仅加 delete；12 加 router；结案 README 写清**启动目录以 12 为准** |
| Postman 依赖本机服务 | CI 难跑 | pytest TestClient 主验收；Postman 人工集成 |

---

## 本周执行顺序（建议）

> 每完成一小阶段：**勾选 checklist → 填写完成/实现说明 → 补齐对应 notebook → 再进下一阶段**。

1. **阶段 0** 骨架 + .env + **复制样本进 Dataset（旧阶段不动）** + 共用 11 单例 + **smoke C0 / C0.5**  
2. **阶段 1** Store.delete + 会话 REST + 与 /qa 同 Store 联调 + **C1**  
3. **阶段 2** stats + **C2**  
4. **阶段 3** DocumentIn（读 Dataset 样本索引）+ **C3**  
5. **阶段 4** pytest + Postman + OpenAPI + 部署文档 + **smoke C4**  
6. **阶段 5** **pi-ops-full.ipynb** 全量仿真 + 
un_full_ops_smoke.py  
7. **阶段 6** 交付收尾（README / 可选报告 / 双 notebook 复核）

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-07-27 | 创建阶段 12 schedule.md，对齐任务书与 11 已交付 API，待启动实施 |
| 2026-07-27 | **计划修订（习惯层）**：notebook 改为贯穿式 C0–C4（对齐 09/11）；原「阶段 5=Notebook 联调与交付」改为「交付收尾」；各小阶段预留完成说明 / 实现说明；.env.example 归阶段 0，阶段 4 做变量文档化与集成验收 |
| 2026-07-27 | **计划修订（内容层）**：对照 11 源码定稿——共用 SessionStore/log 单例；补 delete；会话对外 	urns 非 role 双条；stats 区分 chunk/文档；doc_id=pmcid；收紧 3001；砍会话列表与公开 messages；验证用例对齐 QA 自动新建 vs GET 3002 |
| 2026-07-27 | **计划修订（样本统一 + 4.5）**：样本 **复制**进 Dataset（不改 03/04）；**不进 Git**，README 写来源/重建；曾设阶段 4.5 全量抽检 |
| 2026-07-27 | **样本策略确认**：明确 copy-only、不影响既往阶段、无 gitignore 例外 |
| 2026-07-27 | **计划修订（全量升格）**：原 4.5 → **阶段 5**；新建 **pi-ops-full.ipynb**；原交付 → **阶段 6**；澄清 document_count≠阻碍 full chunk_count |
