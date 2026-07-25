# 11 服务化与接口开发第一部分 — 执行计划

> **状态：✅ 已完成（阶段 0–5 · 2026-07-25）**
>
> **本阶段范围（任务书）**：搭建 **FastAPI 应用骨架**（统一响应、错误码、全局异常、日志、健康检查）；开发 **问答接口**（同步 + 流式），集成已有 RAG 流水线，支持会话关联与调用日志。
>
> **上游依赖**：
> - 10：`ConstrainedGenerationPipeline`（优先）/ 约束校验结果
> - 08：`MedicalGenerationPipeline`、`LLMGenerator`（流式若需扩展）
> - 09：缓存 / 批量（可选挂载，本周非必须）
> - 01：Ollama `http://127.0.0.1:11434`

---

## 任务书目标对照

| 任务书要求 | 本阶段交付 |
|------------|------------|
| FastAPI 应用骨架 | `app/main.py` + `uvicorn` 启动入口 |
| 统一响应 `ResponseModel` + 分页模型 | `app/schemas/response.py` |
| 错误码枚举（1001/2001/3001/4001…） | `app/core/error_codes.py` |
| 全局异常处理 | `app/core/exceptions.py` + handlers |
| 日志与健康检查 | `app/core/logging.py`；`GET /health` |
| 同步问答接口 | `POST /api/v1/qa` |
| 流式问答接口 | `POST /api/v1/qa/stream`（SSE） |
| 集成 RAG 流水线 | 调用 10/08 pipeline |
| 会话管理（`session_id`） | 内存 SessionStore（首版）；接口预留 |
| 参数校验（query / top_k） | Pydantic 请求模型 |
| 调用日志（request_id、耗时、状态） | 中间件 + `outputs/logs/qa_*.jsonl` |

---

## 关键约束与设计决策（启动前）

| 项 | 决策 | 说明 |
|----|------|------|
| Web 框架 | **FastAPI + Uvicorn** | 任务书指定；异步友好，便于 SSE |
| 默认流水线 | **10 `ConstrainedGenerationPipeline.from_mode`** | 已含检索+生成+约束；可配置回退 08（需自行注入依赖） |
| 挂载入口 | `pipeline.run(query)` → 映射 `answer` / `sources` / `constraint_checks` | **不要**把 09 `PipelineWithEval` 当主问答 API（强制要 `ground_truth_entry`） |
| 验证模式 | 服务进程默认 **`mode=sample`**；`full` 仅配置显式打开 | **禁止**每个请求随意切换 mode（会触发重建 pipeline）。**收尾全量抽检**步骤与 Dataset 清单见 [`笔记/11笔记.md`](../笔记/11笔记.md) **Q3**（决定做时再启用进阶段 5） |
| 统一响应 | `{ code, message, data, request_id, timestamp }` | `code=0` 成功；非 0 为错误码 |
| HTTP × 业务码 | 参数错误：**HTTP 400** + body `code=1001` | 覆盖 FastAPI 默认 422，避免客户端两套错误形态 |
| 流式协议 | **SSE**（`text/event-stream`） | 事件：`meta` / `token` / `done` / `error` |
| **流式实现（MVP）** | **默认伪流式**（先同步 `run`，再按句/窗口推 `token`，最后 `done`） | 08 `LLMGenerator.generate` 硬编码 `stream=False`；10 多步+重试与真 token 流冲突大。真流式列为后续，本周不阻塞验收 |
| 会话存储 | 进程内 dict + TTL + `max_turns` | 任务书「结合会话管理」→ 最小可用；持久化后续 |
| **会话如何影响生成（MVP）** | **Store 必做**；注入生成 **轻量可选** | 08/10 `run(query)` **无** `session_history`。MVP：① 存轮次并回传 `session_id`；② 可选把最近 N 轮压成短文本**前缀拼进 query** 再 `run`（不改上游源码）。不做多轮 prompt 改造 |
| `top_k` | API 校验保留；映射为检索 **`top_k_final`**（若可写） | 10/08 `run` **不收** `top_k`；实现时在 `rag_service` 内临时改 `retrieval_pipeline.top_k_final` 或截断返回 `sources`。勿假装 pipeline 已有该参数 |
| 请求体 `mode` / `stream` | **请求体不带 `stream`**（用独立路径 `/qa/stream`）；`mode` 默认忽略或仅允许等于进程配置 | 避免「每请求换库 / 同步接口带流式开关」 |
| 同步阻塞 | `def` 路由或 `run_in_executor` | `pipeline.run` 为同步长耗时，勿在 async 路由里直接阻塞事件循环 |
| `/ready` | **建议做**（轻量） | 返回 pipeline 是否已加载；与 `/health`（进程活）分离 |
| 认证 | 错误码预留 `2001`；本周 **不做真实鉴权** | 避免范围膨胀；header 可预留 |
| 日志落点 | 控制台 + JSONL 文件 | 不强制数据库；结构便于后续入库 |
| bootstrap | 参考 10：挂 10→08→… 时注意 `config` 撞名 | `sys.path` 顺序与 10 `bootstrap` 同策略 |
| 本阶段边界 | **不做** 前端、Docker 生产编排、改写 08/10 内核、09 评估主路径 | 属后续服务化 / 上游增强 |

### 上游接口事实（内容层对齐用）

| 上游 | 可调用形态 | 本周注意 |
|------|------------|----------|
| 10 `ConstrainedGenerationPipeline` | `from_mode("sample"\|"full")`；`run(query, fixture_chunks=None) -> dict` | 有 `constraint_checks` / `retry_count` / `repaired`；**无** stream / session |
| 08 `MedicalGenerationPipeline` | 需自备 retrieval/assembler/llm；`run(query) -> dict` | 无 `constraint_checks`；无 `from_mode` |
| 08 `LLMGenerator` | `generate` / `generate_json`；`ping` | **`stream: False` 写死**；无 `generate_stream` |
| 09 `PipelineWithEval` | `run_with_cache_and_eval(..., ground_truth_entry=必填)` | **不**作 `/qa` 主路径；缓存可后续可选外包 |

### 响应字段映射（10 → API）

| API `data` 字段 | 来源 |
|-----------------|------|
| `answer` / `sources` | `result["answer"]` / `result["sources"]` |
| `generation_metrics` | `result["generation_metrics"]` |
| `constraint_checks` | `result["constraint_checks"]`（走 10 时） |
| `retry_count` / `repaired` | 可选透出，便于排障 |
| `session_id` | SessionStore，非 pipeline 字段 |

---

## 端到端数据流

```
Client
  │  POST /api/v1/qa  { query, top_k?, session_id? }
  ▼
FastAPI
  │  校验 query / top_k → 失败则 HTTP 400 + code=1001
  │  分配 request_id
  │  SessionStore：无 session_id 则 create；有则 get（过期 → 3002 或新建，实现时二选一并写清）
  │  （可选 MVP）最近 N 轮摘要前缀拼进 effective_query
  ▼
rag_service
  │  可选：设置 retrieval.top_k_final ≈ top_k
  │  ConstrainedGenerationPipeline.run(effective_query)   # 同步
  │  异常映射：Ollama/httpx → 4001；其它 → 4002
  ▼
ResponseModel
  │  data: { answer, sources, metrics, constraint_checks?, session_id, ... }
  │  SessionStore.append(turn)；qa_logger 写耗时/状态
  ▼
Client

流式分支（MVP = 伪流式）：
  POST /api/v1/qa/stream
    → 同上跑完 pipeline.run（或后台跑）
    → SSE: meta → token*（对 answer 分块）→ done(sources/metrics)
    → 异常: event error + 标准错误码 JSON
```

---

## 模块设计

### 目录结构（规划）

```text
11 服务化与接口开发第一部分/
├── 任务.txt
├── schedule.md
├── requirements.txt                 # fastapi, uvicorn, pydantic, sse-starlette(可选)
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI() + 路由挂载 + 异常/中间件
│   ├── config.py                    # 端口、模式、日志路径、pipeline 开关
│   ├── core/
│   │   ├── error_codes.py           # ErrorCode 枚举
│   │   ├── exceptions.py            # AppException + handlers
│   │   ├── logging.py               # 结构化日志
│   │   └── middleware.py            # request_id / 耗时
│   ├── schemas/
│   │   ├── response.py              # ResponseModel / PageModel
│   │   └── qa.py                    # QARequest / QAResponseData
│   ├── api/
│   │   ├── health.py                # GET /health
│   │   └── qa.py                    # /qa、/qa/stream
│   ├── services/
│   │   ├── rag_service.py           # 封装 10/08 pipeline
│   │   ├── session_store.py         # session_id → 历史轮次
│   │   └── qa_logger.py             # 问答调用落盘
│   └── deps.py                      # FastAPI Depends（拿 service 单例）
├── scripts/
│   └── run_api.py                   # uvicorn 启动封装
├── notebooks/
│   └── api-smoke.ipynb              # C0–C4 贯穿各小阶段（非收尾才补）
├── tests/
│   ├── test_health.py
│   ├── test_response_model.py
│   ├── test_error_handlers.py
│   └── test_qa_api.py               # TestClient；mock pipeline
└── outputs/
    └── logs/
        └── qa_calls.jsonl
```

### 统一响应与错误码（草案）

```python
class ResponseModel(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any | None = None
    request_id: str
    timestamp: str


class PageModel(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class ErrorCode(IntEnum):
    OK = 0
    PARAM_ERROR = 1001
    AUTH_FAILED = 2001
    DOC_NOT_FOUND = 3001
    MODEL_CALL_FAILED = 4001
    PIPELINE_FAILED = 4002
    SESSION_NOT_FOUND = 3002
    INTERNAL_ERROR = 5000
```

### 问答请求 / 响应（草案）

```python
class QARequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=20)
    session_id: str | None = None
    # 不设 stream（用 /qa/stream）；不设 per-request mode（用进程 config）


class QAResponseData(BaseModel):
    answer: str
    sources: list[dict]
    session_id: str | None
    generation_metrics: dict | None = None
    constraint_checks: dict | None = None  # 走 10 时
    retry_count: int | None = None
    repaired: bool | None = None
```

### API 一览（本周）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 进程存活；可选探测 Ollama |
| GET | `/ready` | pipeline 是否已加载（建议实现；未加载可 503） |
| POST | `/api/v1/qa` | 同步问答 |
| POST | `/api/v1/qa/stream` | 流式问答（SSE；MVP 伪流式） |
| GET | `/api/v1/sessions/{session_id}` | （可选）查看会话摘要 |

---

## 分阶段执行

### Notebook 贯穿策略 🔄

> 对齐 09 / 10：`api-smoke.ipynb` **不是**收尾才补的演示章，而是**随各小阶段增量追加**的可视化成果与测试入口。

- [x] 采用**单一 notebook 贯穿式开发**：`notebooks/api-smoke.ipynb`
- [ ] 每完成一个小阶段，立即补齐对应 C* 单元并保存输出，**不等到最后统一补**
- [x] 阶段与单元映射：

| 小阶段 | Notebook | 作用 |
|--------|----------|------|
| 0 骨架 | C0 / C0.5 | 目录与依赖、`config` 加载、uvicorn / `app` 可 import；可选探活 |
| 1 统一响应 / 异常 / 健康 | C1 | `ResponseModel` 样例、错误码 1001 形态、`GET /health` |
| 2 RAG 服务 + 会话 | C2 | `rag_service.answer`（可 mock）+ `SessionStore` 增删查 |
| 3 同步问答 | C3 | `POST /api/v1/qa` 成功 / 参数错误 / 带 `session_id` 两轮 |
| 4 流式问答 | C4 | `POST /qa/stream`：meta → token → done（或 error） |
| 5 交付收尾 | （全量复核 C0–C4） | 与代码一致性检查；实跑 1–2 条 + 日志确认；**不新增演示章** |

> 每完成一小阶段工作流：**勾选 checklist → 填写完成说明 / 实现说明 → 补齐对应 notebook C* → 再进下一阶段**。

### 阶段 0：环境与骨架 ✅

- [x] 创建目录结构（`app/`、`scripts/`、`tests/`、`notebooks/`、`outputs/logs/`）
- [x] `requirements.txt`：`fastapi`、`uvicorn[standard]`、`pydantic`、`httpx`
- [x] `app/config.py`：host/port、默认 `retrieval_mode=sample`、日志路径、`pipeline_backend=constrained10`
- [x] `app/bootstrap.py`（或等价）：挂 10/08 `sys.path`，避免与 06/09 `config` 撞名（对齐 10）
- [x] `scripts/run_api.py`：`uvicorn app.main:app --reload`
- [x] Notebook **C0**：环境初始化 + import `app` / `config` + 依赖自检
- [x] Notebook **C0.5**：Ollama 探活（`LLMGenerator.ping` 或 httpx）；确认 10 模块可 import（**不**强制冷启全量库）
- [x] `tests/test_stage0_skeleton.py`：**5 passed**
- [x] 空壳 `app/main.py`：`GET /` 返回 stage0 元信息（`/health` 留给阶段 1）

**阶段 0 完成说明**

- 本阶段搭好 11 工程骨架：目录、依赖、`config`（默认 sample）、`bootstrap`（挂 05–10，`app` 包优先）、uvicorn 启动脚本。
- 贯穿式 notebook 已建 **C0 / C0.5**：依赖自检、`TestClient` 调 `/`、Ollama 可选探活、确认 `ConstrainedGenerationPipeline` 可 import。
- 此阶段**未**实现统一响应信封、**未**挂 RAG 问答路由——只有可启动的空壳 FastAPI。

**阶段 0 实现说明（代码路径 / 函数 / 方法）**

- `app/config.py`
  - `_env(name, default) -> str`：读环境变量；空串回退到 `default`。
  - `Stage11Config`（frozen dataclass）：进程级配置（**非**每请求）。关键字段：
    - `host` / `port`：uvicorn 监听（默认 `127.0.0.1:8000`）
    - `retrieval_mode`：默认 `"sample"`（可用 `MED_RAG_RETRIEVAL_MODE` 或 `STAGE11_RETRIEVAL_MODE` 覆盖为 `full`）
    - `pipeline_backend`：默认 `"constrained10"`（可回退规划值 `"medical08"`）
    - `log_dir`：默认 `outputs/logs`
    - `ollama_base_url` / `ollama_model`：探活与后续生成
    - `session_ttl_seconds` / `session_max_turns` / `query_max_length` / `top_k_*`：阶段 2+ 预留
  - `DEFAULT_CONFIG = Stage11Config()`：模块加载时固化一份默认实例。
- `app/bootstrap.py`
  - **思路**：notebook/tests/uvicorn 工作目录不一；06/09/10 都有同名 `config`，必须按「后插入靠前」让 **10 的业务模块可被 import**，同时 **`app` 包不能被上游 `src` 盖住**。
  - `project_root(start=None) -> Path`：从 cwd / notebooks / stage11 目录推断仓库根 `谷歌/`。
  - `stage11_dir(start=None) -> Path`：返回阶段 11 目录。
  - `bootstrap_paths(start=None) -> StagePaths`：
    - **输入**：可选起始路径
    - **过程**：先插入 stage11 根 → 再按 05→10 插入各 `src`（`insert(0)`，故 10 在上游最前）→ **再次**把 stage11 根置顶
    - **输出**：含 `root` / `stage05`…`stage11` 的路径字典；副作用是改写 `sys.path`
- `app/probe.py`（不加载 Chroma/BM25）
  - `probe_ollama(config=None, *, timeout=5.0) -> dict`：
    - **思路**：只打 Ollama `GET /api/tags`，失败也返回字典，不抛异常（探活友好）
    - **输入**：可选 `Stage11Config`、超时秒数
    - **输出**：成功 `{ok, base_url, model_configured, model_present, models_sample}`；失败 `{ok:False, error, ...}`
  - `try_import_stage10() -> dict`：
    - **思路**：验证 bootstrap 后能否 `from constrained_pipeline import ConstrainedGenerationPipeline`
    - **输出**：`{ok, class, module}` 或 `{ok:False, error}`；**不**调用 `from_mode` / `run`
- `app/main.py`（阶段 0 空壳；阶段 1 已扩展，见下）
  - 阶段 0 时：`FastAPI(...)` + `GET /` 返回服务元信息占位。
- `scripts/run_api.py`
  - `main()`：`bootstrap_paths` → 解析 `--host/--port/--reload|--no-reload` → `uvicorn.run("app.main:app", ...)`
  - **输入**：命令行参数；默认读 `DEFAULT_CONFIG`
  - **输出**：阻塞运行 HTTP 服务（reload 时监视 stage11 目录）
- `notebooks/api-smoke.ipynb`
  - **C0**：打印 `sys.executable` → 缺包则 `pip install -r requirements.txt` 到**当前内核** → bootstrap → 断言 config 默认 sample
  - **C0.5**：`probe_ollama` + `try_import_stage10`（Ollama 可选；stage10 import 必过）
- `tests/test_stage0_skeleton.py`：bootstrap 置顶、config 默认、`import app.main`、根路径、stage10 可 import
- `requirements.txt`：`fastapi`、`uvicorn[standard]`、`pydantic`、`httpx`、`pytest`

### 阶段 1：统一响应、错误码、全局异常、日志、健康检查 ✅

- [x] `ResponseModel` / `PageModel`
- [x] `ErrorCode` 枚举（至少 1001 / 2001 / 3001 / 4001 + 内部 5000）
- [x] `AppException(code, message, detail=None)`
- [x] 全局 handler：`AppException` / `RequestValidationError`→**1001** / 未捕获→**5000**
- [x] 中间件：生成 `request_id`、记录耗时、写入响应头 `X-Request-Id`
- [x] 结构化日志（console + 可选文件）
- [x] `GET /health` → `{ status: "ok", ollama?: bool }`（进程活；Ollama 可选探测）
- [x] （建议）`GET /ready` → pipeline 是否已加载
- [x] 单元测试：校验失败返回 **400 + code=1001** 形态；健康检查 200
- [x] Notebook **C1**：构造 `ResponseModel` 成功/失败样例；`TestClient` 调 `/health`；故意触发校验错误看 1001 信封
- [x] 校验演示路由：`POST /api/v1/echo`（阶段 1 契约演示，非产品问答）

**阶段 1 完成说明**

> 用大白话说：阶段 0 只是把店门开了（空壳能启动）；**阶段 1 是把前台规矩定好**——客人来了怎么回执、点错菜怎么拒、店开没开怎么查。还**不能点医学问答菜**（那是阶段 2–3）。

- **统一小票（ResponseModel）**  
  不管成功还是失败，返回 JSON 都长一个样：`code`（0=成功，非 0=错误码）、`message`（人话说明）、`data`（真正内容）、`request_id`（这单的单号）、`timestamp`。  
  另外响应头里有 `X-Request-Id`，方便你对照日志「刚才那一单是哪笔」。

- **拒单话术（错误码 + 全局异常）**  
  以前框架默认参数错会甩一坨 422；现在统一成：**HTTP 400 + 业务码 1001**（参数错误）。  
  业务自己抛的错用 `AppException`（比如以后模型挂了 → 4001）；真崩了没接住 → **5000**，且不会把整段堆栈甩给调用方。  
  → 前端/脚本以后只认一种错误长相，不用猜。

- **探活灯（/health、/ready）**  
  - `/health`：店还开着吗？（进程活着就 ok；可选再问一句后厨 Ollama 在不在）  
  - `/ready`：后厨流水线装好了吗？阶段 1 结束时还是 **false**（阶段 2 挂上 RAG 才会变 true）

- **你现在能亲手看到的成果**  
  1. 浏览器或 `/docs` 打开 `/health`，看到带 `code=0` 和 `request_id` 的标准小票  
  2. notebook **C1**：故意往 `/api/v1/echo` 发空字符串 → 拿到 **400 + code=1001**（不是乱码 422）  
  3. `outputs/logs/api.log` 里能看到带 request_id、耗时的访问记录  

- **本阶段刻意没做的**  
  还没有真正的 `POST /api/v1/qa`，也不会去检索文献、调大模型。阶段 1 只解决「怎么规规矩矩地对外说话」，不解决「怎么答医学题」。

**阶段 1 实现说明（代码路径 / 函数 / 方法）**

- `app/schemas/response.py`
  - `utc_now_iso() -> str`：UTC 时间戳字符串，写入每条响应的 `timestamp`。
  - `ResponseModel[T]`：统一信封字段 `code` / `message` / `data` / `request_id` / `timestamp`。
  - `PageModel`：分页容器 `items/total/page/page_size`（本周问答未用，预留给列表类接口）。
  - `success_response(data, *, request_id, message="ok") -> ResponseModel`：
    - **思路**：业务成功时统一 `code=0`
    - **输入**：任意可序列化 `data`、必填 `request_id`
    - **输出**：完整成功信封
  - `error_response(*, code, message, request_id, data=None) -> ResponseModel`：
    - **思路**：失败也走同一信封，便于客户端只解析一种 JSON
    - **输入**：业务码、文案、`request_id`、可选 `data`（如校验 errors）
    - **输出**：错误信封（HTTP 状态由 handler 另定）
- `app/core/error_codes.py`
  - `ErrorCode(IntEnum)`：`0/1001/2001/3001/3002/4001/4002/5000`
  - `ERROR_MESSAGES`：码 → 默认英文短文案
  - `http_status_for(code) -> int`：
    - **映射**：1001→400；2001→401；3001/3002→404；4001/4002→502；5000→500；0→200
- `app/core/exceptions.py`
  - `AppException(code, message=None, detail=None)`：
    - **思路**：业务层抛稳定错误码，而不是裸 HTTPException
    - **输入**：`ErrorCode`；可选覆盖文案；可选 `detail`（进响应 `data.detail`）
  - `register_exception_handlers(app)`：注册四类 handler
    - `AppException` → `error_response` + `http_status_for(code)`
    - `RequestValidationError` → **强制 HTTP 400 + code=1001**，`data.errors=exc.errors()`（覆盖默认 422）
    - `StarletteHTTPException` → 按 status 粗映射业务码 + 同构信封
    - 未捕获 `Exception` → HTTP 500 + code=5000，`data.error_type`（不回传堆栈正文）
- `app/core/middleware.py`
  - `RequestContextMiddleware.dispatch(request, call_next)`：
    - **思路**：每个请求一个可追踪 id，并记录耗时
    - **输入**：入站请求；若带 `X-Request-Id` 则复用，否则 `uuid4`
    - **过程**：写入 `request.state.request_id` → 调下游 → 响应头加 `X-Request-Id`、`X-Response-Time-Ms` → info 日志
    - **输出**：原响应（已带头）；异常向上抛给 handler
- `app/core/logging.py`
  - `setup_logging(config=None)`：幂等配置 logger `med_rag_api`（stdout + `log_dir/api.log` 轮转）
  - `get_logger(name=None) -> Logger`：返回 `med_rag_api` 或子 logger
- `app/state.py`
  - `AppRuntimeState` / 单例 `RUNTIME`：`pipeline_loaded` / `pipeline_mode` / `pipeline_backend` / `last_error`
  - **用途**：`/ready` 读取；阶段 2 懒加载成功后置 `pipeline_loaded=True`
- `app/api/health.py`
  - `GET /health?check_ollama=false`：
    - **思路**：进程存活；Ollama 默认不探（避免拖慢探活），需要时 `check_ollama=true`
    - **输出**：`ResponseModel`，`data={status, version, retrieval_mode, pipeline_backend, ollama?, ollama_detail?}`
  - `GET /ready`：
    - **输出**：`data={ready, pipeline_loaded, pipeline_mode, pipeline_backend, last_error}`；阶段 2 前 `ready=false`
  - `POST /api/v1/echo`（契约演示，非产品问答）：
    - **输入**：`EchoBody{message: str, 1..20 字符}`
    - **成功**：`code=0, data={echo}`；**失败**（空串等）走校验 handler → 1001
  - `GET /api/v1/_demo_error?kind=param|model|internal`：单测用，分别触发 1001 / 4001 / 未捕获 5000
- `app/main.py`
  - 启动时 `setup_logging` → 挂 `RequestContextMiddleware` → `register_exception_handlers` → `include_router(health_router)`
  - `GET /`：返回 `success_response`，`data.stage="1-contract"`
- `tests/`
  - `test_response_model.py`：信封构造与 PageModel
  - `test_health.py`：`/health` 200 + request_id 头透传；`/ready` 未加载；`/` 信封
  - `test_error_handlers.py`：空 message → 400/1001；AppException；未捕获 → 5000
- `notebooks/api-smoke.ipynb` **C1**：手构成功/失败信封 → TestClient 打 `/health` `/ready` → 故意空 echo 看 1001
- 全量 pytest：**19 passed**（含阶段 0）

### 阶段 2：RAG 服务封装与会话存储 ✅

- [x] `rag_service.py`：懒加载 / 单例持有 pipeline
  - [x] 工厂：`ConstrainedGenerationPipeline.from_mode(config.retrieval_mode)`（默认 sample）
  - [x] `answer(query, top_k=None, session_history=None) -> dict`
  - [x] `top_k`：尽量写入 `retrieval_pipeline.top_k_final`；若不可达则截断返回 `sources[:top_k]` 并在 metrics 注明
  - [x] `session_history`：MVP 可将最近轮次格式化为短前缀拼进 `effective_query`；**不**调用不存在的 `run(..., history=)`
  - [x] 异常映射：`httpx`/连接/超时 → `4001`；其它流水线异常 → `4002`
- [x] `session_store.py`：
  - [x] `create()` / `get(session_id)` / `append(session_id, turn)`
  - [x] TTL + `max_turns`（如 10）；过期策略写清（3002 vs 自动新建）
- [x] Notebook **C2**：优先 **mock pipeline** 测封装；可选 sample 真跑 1 条；`SessionStore` create → append → get 演示
- [x] `app/deps.py`：`get_rag_service` / `get_session_store`（lru_cache 单例）
- [x] 单元测试：`test_session_store.py` + `test_rag_service.py`；全量 pytest **31 passed**

**阶段 2 完成说明**

> 大白话：阶段 1 是前台规矩；**阶段 2 是把「后厨传菜口」和「桌号记事本」做好**。还没有正式的点餐窗口 `POST /qa`（那是阶段 3），但厨房已经能按单做菜、前台能记这桌点过什么。

- **后厨叫号口（`RagService`）**  
  - 懒加载：第一次 `answer` 才真正 `ConstrainedGenerationPipeline.from_mode(sample)`（可注入 mock，方便测）。  
  - 加载成功会把 `/ready` 用的 `RUNTIME.pipeline_loaded=True`。  
  - 多轮：上游 08/10 **没有** `session_history` 参数 → MVP 把最近几轮压成短文本**前缀拼进 query** 再 `run`。  
  - `top_k`：能改检索的 `top_k_final` 就改，改不了就截断返回的 `sources`。  
  - 失败分类：Ollama/网络类 → **4001**；其它流水线炸了 → **4002**。

- **桌号档案（`MemorySessionStore`）**  
  - `create` 发新桌号；`append` 记一轮问答；超 `max_turns` 只留最近 N 轮；超时 TTL 视为过期删除。  
  - **过期/不存在**：`get` → `None`；`require` / `append` 到无效桌号 → **3002**。阶段 3 HTTP 层可自选「报 3002」或「自动新建」。

- **你现在能看到的成果**  
  1. notebook **C2**：mock 跑通 `answer` + 会话两轮 + 前缀进 `effective_query`  
  2. （可选）把 `RUN_LIVE_SAMPLE=True` 真跑 1 条 sample（需 Ollama + 样本库）  
  3. 单测 31 passed，**不依赖**全量 610 万

- **本阶段刻意没做的**  
  尚未挂 `POST /api/v1/qa`；会话仍在内存，进程退出即丢。

**阶段 2 实现说明（代码路径 / 函数 / 方法）**

- `app/services/session_store.py`
  - `SessionTurn` / `SessionRecord`：一轮问答与整段会话的数据结构；`to_dict()` 便于调试。
  - `MemorySessionStore.__init__(config)`：进程内 `dict` + `RLock`。
  - `create() -> SessionRecord`：**输入**无；**输出**新 `session_id`（uuid）记录。
  - `get(session_id) -> SessionRecord | None`：缺失或超过 `session_ttl_seconds`（按 `updated_at`）→ 删除并返回 `None`。
  - `require(session_id) -> SessionRecord`：同 `get`，失败抛 `AppException(SESSION_NOT_FOUND=3002)`。
  - `append(session_id, turn) -> SessionRecord`：追加一轮；超过 `session_max_turns` 只保留末尾 N 条；刷新 `updated_at`；无效 id → 3002。
  - `format_session_prefix(turns, max_turns=3, answer_clip=200, max_chars=800) -> str`：
    - **思路**：不改 08/10，只造一段可拼进 query 的短上下文
    - **输出**：含 `[Conversation context]` / `Previous Q/A` / `[Current question]` 的前缀；空 turns → `""`
- `app/services/rag_service.py`
  - `RagService.__init__(config, pipeline=None, pipeline_factory=None, inject_history=True)`：可注入假 pipeline（单测/C2）。
  - `ensure_pipeline() -> PipelineLike`：懒加载；成功写 `RUNTIME`；失败 → `PIPELINE_FAILED(4002)`。
  - `_default_factory()`：`constrained10` → `ConstrainedGenerationPipeline.from_mode(retrieval_mode)`；`medical08` 暂未接线（明确 4002）。
  - `answer(query, *, top_k=None, session_history=None) -> dict`：
    - **输入**：用户问题；可选 top_k（默认 config）；可选历史 turns
    - **过程**：空 query/非法 top_k → 1001；拼 `effective_query`；`_apply_top_k`；`pipeline.run`；异常映射 4001/4002；`finally` 恢复 top_k；必要时截断 sources
    - **输出**：规范化 dict（`answer/sources/constraint_checks?/metrics?` + `effective_query/top_k_applied/top_k_mode/query`）
  - `_apply_top_k` / `_restore_top_k`：优先改 `retrieval_pipeline.top_k_final`；否则标记 `truncate_sources`
  - `_normalize_result`：支持 `to_dict()` 或纯 dict
- `app/deps.py`
  - `get_session_store()` / `get_rag_service()`：`lru_cache` 进程单例，供阶段 3 `Depends`
  - `reset_singletons()`：测试清缓存
- `tests/test_session_store.py`：增删查、max_turns、TTL→3002、prefix 文案
- `tests/test_rag_service.py`：mock top_k、历史前缀、4001/4002、空 query/越界 top_k
- `notebooks/api-smoke.ipynb` **C2**：SessionStore 演示 + mock `RagService`；可选 live sample 开关
- 全量 pytest：**31 passed**

### 阶段 3：同步问答接口 ✅

- [x] `POST /api/v1/qa`（同步 `def` 或 executor，避免堵事件循环）
- [x] 参数校验：`query` 非空且 `≤ max_length`；`top_k ∈ [1, 20]` → **1001**
- [x] 若传 `session_id`：关联 Store；若无则新建并回传
- [x] 成功：`ResponseModel(code=0, data=QAResponseData, ...)`；透出 `constraint_checks`（走 10 时）
- [x] `qa_logger`：写 `request_id`、耗时、状态、query 摘要（注意脱敏）
- [x] TestClient：mock `rag_service` 测参数错误与成功路径
- [x] Notebook **C3**：`POST /qa` 合法 query；空 query / 非法 `top_k` → 1001；带 `session_id` 连问两轮（断言 Store 有两轮）；确认日志行
- [x] （附加）`GET /api/v1/sessions/{session_id}` 查看会话摘要
- [x] 全量 pytest：**35 passed**

**阶段 3 完成说明**

> 大白话：前台终于能**正式接单**了——客人 `POST /api/v1/qa` 问一句，就能拿到答案、文献来源、会话桌号；点错参数会按阶段 1 的规矩拒单（1001）。

- **同步点餐**：一次请求等整条 RAG（10 约束流水线）跑完，返回统一小票；`data` 里有 `answer` / `sources` / `constraint_checks` / `session_id` 等。  
- **会话**：不带 `session_id` → 新建；带了且有效 → 把历史前缀塞进生成；过期/不存在 → **自动新建桌号**（比硬 3002 更友好）。第二轮 Store 里应有 2 条 turns。  
- **调用账本**：每次写入 `outputs/logs/qa_calls.jsonl`（query 只留预览截断，不落全文）。  
- **本阶段仍用 mock 验收契约**；真 sample/Ollama 可在阶段 5 或手动去掉 override 后实跑（注意 ~2 分钟冷启）。

**阶段 3 实现说明（代码路径 / 函数 / 方法）**

- `app/schemas/qa.py`
  - `QARequest`：`query`（1..2000）、`top_k`（1..20，默认 5）、可选 `session_id`
  - `QAResponseData`：`answer/sources/session_id` + 可选 `generation_metrics/constraint_checks/retry_count/repaired/top_k_*`
- `app/services/qa_logger.py`
  - `QACallLogger.log(...)`：**输入** request_id、query、status、latency_ms、code…；**输出** 追加一行 JSONL；`query_preview` 默认截断 80 字
- `app/api/qa.py`
  - `_resolve_session(store, session_id)` → `(sid, history, created_new)`；缺失/过期自动 `create`
  - `POST /api/v1/qa`（同步 `def`）：Depends 取 rag/store/logger → `rag.answer` → `store.append` → `success_response`；异常先写错误日志再抛
  - `GET /api/v1/sessions/{session_id}`：`store.require` 后返回 turn 摘要（无效 → 3002）
- `app/deps.py`：新增 `get_qa_logger()`；`reset_singletons` 同步清理
- `app/main.py`：挂载 `qa_router`；根 `stage` → `3-qa`
- `tests/test_qa_api.py`：mock 成功 / 空 query / 坏 top_k / 两轮会话 + 日志文件
- `notebooks/api-smoke.ipynb` **C3**：dependency_overrides 演示全路径
- 全量 pytest：**35 passed**

### 阶段 4：流式问答接口 ✅

- [x] `POST /api/v1/qa/stream` → SSE（`StreamingResponse`；未引入 `sse-starlette`）
- [x] 事件约定：
  - [x] `event: meta` — request_id / session_id / `stream_mode: "pseudo"`
  - [x] `event: token` — 增量文本 `{"text": ...}`
  - [x] `event: done` — 完整 answer / sources / metrics / constraint_checks
  - [x] `event: error` — 标准错误码 JSON（与同步信封字段对齐）
- [x] **MVP 实现定稿：伪流式**
  - [x] 调用与同步相同的 `rag_service.answer`（完整约束闭环）
  - [x] 将 `answer` 按句或固定窗口切分推送 `token`
  - [x] 文档 / notebook / OpenAPI 标明：非 Ollama token 级真流式
- [x] （可选后续，本周不阻塞）探测/扩展 `LLMGenerator` 真流式 — **未做**，不阻塞验收
- [x] 结束时写调用日志（总耗时与状态；含 `stream_mode`）
- [x] Notebook **C4**：消费 SSE；展示 meta → token* → done；异常走 error；打印 `stream_mode`
- [x] 全量 pytest：**41 passed**

**阶段 4 完成说明**

> 大白话：前台可以「边出菜边端上桌」了——但厨子仍是**整道菜做好再按块端**（伪流式），不是炉火边炒边递（真 token 流）。API 形态是 SSE，验收不依赖改 08。

- **伪流式闭环**：先 `meta`（桌号/request_id/`stream_mode=pseudo`）→ 同步跑完 `rag.answer` → 把 answer 切块推 `token` → `done` 带齐 sources/metrics/`constraint_checks`。  
- **异常**：管道/模型失败在流内发 `event: error`（HTTP 仍 200）；入参校验失败仍在流开始前返回 **JSON 400 + 1001**。  
- **日志**：成功/失败都写 `qa_calls.jsonl`，并带 `stream_mode=pseudo`。  
- **真流式**：本周不做；若以后接 Ollama `stream=True`，须单独说明与 10 约束重试的冲突。

**阶段 4 实现说明（代码路径 / 函数 / 方法）**

- `app/services/sse_pseudo.py`
  - `format_sse(event, data)` → SSE 文本帧
  - `chunk_answer_pseudo` / `iter_pseudo_tokens` → 句读 + 固定窗口切块
- `app/api/qa.py`
  - `POST /api/v1/qa/stream` → `StreamingResponse`（`text/event-stream`）；响应头 `X-Stream-Mode: pseudo`
  - 常量 `STREAM_MODE = "pseudo"`；OpenAPI description 标明非真 token 流
- `app/config.py`：`stream_chunk_chars`（环境变量 `STAGE11_STREAM_CHUNK_CHARS`，默认 32）
- `app/main.py`：根 `stage` → `4-stream`；应用描述含伪 SSE
- `tests/test_sse_pseudo.py`、`tests/test_qa_stream.py`：成功路径 / 1001 / error 事件
- `notebooks/api-smoke.ipynb` **C4**
- 全量 pytest：**41 passed**

### 阶段 4.5：全量 Dataset + Ollama 真跑（报告素材）✅

> 插在阶段 4 与 5 之间：最大程度还原未来使用路径（**full 语料 + 真 Ollama + 真实 RagService**）。  
> **不改 API 能力**；产出供阶段 5 写报告。详见笔记 Q3 / notebook **C4.5**。

- [x] 资源自检：`chroma_db_full` + `bm25_full` manifest completed + Ollama 模型在线（`probe_full_dataset`）
- [x] 单例预热 `RagService(retrieval_mode=full).ensure_pipeline()`
- [x] 主线程 `rag.answer` 实跑 1 条（`metformin cardiovascular effects`，`top_k=5`）
- [x] 同 session 第二轮 + 伪 SSE 事件重建
- [x] 热身后 `TestClient` HTTP 探针：`POST /qa` → **200 / code=0**
- [x] 导出 `outputs/reports/full_api_smoke.json` + 4 张 PNG + JSONL
- [x] Notebook **C4.5** + CLI `scripts/run_full_api_smoke.py`
- [x] **最新复跑（报告采用）**：sync **179.53 s** · 第二轮 **214.49 s** · HTTP ≈126 s · `n_token=118`

**阶段 4.5 完成说明**

> 大白话：用**全库 + 真厨子（Ollama）**点了两道菜，确认前台接到的不是样品间玩具库；图和 JSON 已备好给阶段 5 写报告。

- **权威路径**：主线程 `RagService(full)`（避免部分 Windows 中文/云盘路径下 Starlette 线程池 `WinError 6714`）。  
- **最新结果**：sync **179.53 s**（assemble≈151.5 s）；sources 为全量 PMC id；citation/format 通过。  
- **HTTP**：模型热身后 TestClient `/qa` 成功；冷线程池首次加载仍可能踩路径坑（已记入 `windows_note`）。  
- **主轨不变**：契约单测仍用 sample/mock；全量是连通抽检，不是第二次 09 评测。

**阶段 4.5 实现说明（代码路径 / 函数 / 方法）**

- `app/probe.py` → `probe_full_dataset`
- `app/full_smoke.py` → `run_full_http_smoke` / `render_report_figures`
- `scripts/run_full_api_smoke.py`
- `notebooks/api-smoke.ipynb` **C4.5**
- 产物：`outputs/reports/full_api_smoke*`（2026-07-25 实测）

### 阶段 5：交付收尾 ✅

> Notebook 演示已拆入阶段 0–4 + **C4.5**；本阶段做**打包与文档对齐**（报告引用最新 C4.5 图/JSON）。

- [x] Notebook 全量复核：C0–C4 / C4.5 与代码一致；C4.5 运行记录已按**最新实测**回填
- [x] 确认 C4.5 日志含 `request_id` / `latency_ms` / `status`（`qa_calls_full_smoke.jsonl`）
- [x] 更新根目录 `README.md` 阶段 11 条目 → ✅ 已完成
- [x] `docs/服务化接口报告.md`：任务书对照 + 接口一览 + 最新 full live（sync **179.53 s**）
- [x] 勾选本 schedule；进度记录补全收尾日期；根 `stage` → `5-done`；pytest **41 passed**

**阶段 5 完成说明**

> 大白话：店面装修、菜单、点餐口都齐了，还用全库真厨子抽检过；报告与 README 已归档，本周任务书结案。

- **交付包**：契约单测 41 passed · notebook C0–C4.5 · 正式报告 · `outputs/reports/` 图文 · README 阶段 11 ✅。  
- **最新全量抽检**（用户复跑）：sync **179.53 s** · 第二轮 **214.49 s** · HTTP 探针 ok · citation/format 通过。  
- **不再加新接口能力**；后续真流式 / 会话落盘 / 鉴权属服务化后续。

**阶段 5 实现说明（代码路径 / 函数 / 方法）**

- [`docs/服务化接口报告.md`](docs/服务化接口报告.md)
- 根目录 `README.md` 阶段 11 条目（状态 ✅、启动、报告链接）
- `notebooks/api-smoke.ipynb` C4.5 运行记录（最新数字）
- `app/main.py`：`stage=5-done`
- 本文件状态栏 → ✅；pytest **41 passed**

---

## 验证用例（首批）

| # | 场景 | 期望 |
|---|------|------|
| 1 | `GET /health` | 200，`code=0` 或等价 ok |
| 2 | `POST /qa`，`query=""` | 422/业务码 **1001** |
| 3 | `POST /qa`，`top_k=999` | **1001** |
| 4 | `POST /qa`，合法 query | **0** + answer/sources |
| 5 | 带 `session_id` 连问两轮 | 第二轮 **Store 有历史**（可选：effective_query 含前缀）；不要求上游原生多轮 |
| 6 | Ollama 停服时调用 | **4001**，统一错误体 |
| 7 | `/qa/stream` | meta（含 `stream_mode=pseudo`）→ token* → done；异常走 error |
| 8 | 日志 | 每次调用有 request_id、耗时、状态 |
| 9 | 非法 query / top_k | **HTTP 400** + `code=1001`（非裸 422） |

---

## 交付产物清单（预填）

| 产物 | 格式 | 路径 | Git |
|------|------|------|-----|
| FastAPI 应用 | Python | `app/main.py` 等 | ✅ |
| 错误码 / 异常 | Python | `app/core/` | ✅ |
| 问答路由 | Python | `app/api/qa.py` | ✅ |
| RAG / Session 服务 | Python | `app/services/` | ✅ |
| 启动脚本 | Python | `scripts/run_api.py` | ✅ |
| API smoke notebook（贯穿 C0–C4.5） | `.ipynb` | `notebooks/api-smoke.ipynb` | ✅ |
| 单元测试 | Python | `tests/` | ✅ |
| 调用日志样例 | JSONL | `outputs/logs/qa_calls.jsonl` · `outputs/reports/qa_calls_full_smoke.jsonl` | ✅（可脱敏） |
| 全量抽检报告素材 | JSON / PNG | `outputs/reports/full_api_smoke*` | ✅ |
| 正式报告 | Markdown | `docs/服务化接口报告.md` | ✅ |
| OpenAPI | 自动 | `/docs`（Swagger） | ✅ |

---

## 风险与应对

| 风险 | 影响 | 应对（已写入设计决策） |
|------|------|------------------------|
| 把「优先真流式」当验收硬条件 | 08 无 stream，10 多步重试难流式 → 阶段 4 卡住 | **MVP 伪流式定稿**；真流式后续 |
| 假定 `run(session_history=…)` / `run(top_k=…)` | 调用失败或静默忽略 | 会话用 Store + 可选 query 前缀；`top_k` 映射 `top_k_final` 或截断 sources |
| 请求体带 `mode`/`offline` 每请求换库 | 冷启极慢 / 模式名不存在 | **进程级 config**；去掉 per-request mode |
| 用 09 `PipelineWithEval` 做 `/qa` | 缺 `ground_truth` 无法调用 | 主路径只用 10/08 |
| FastAPI 默认 422 | 与业务码 1001 双轨 | handler 统一成 **400 + 1001** |
| async 路由直接 `pipeline.run` | 事件循环卡死 | `def` 路由或 executor |
| Pipeline 冷启动慢 | 首请求超时 | 懒加载 + **`/ready`**；默认 sample |
| 会话无限增长 | 内存/上下文爆 | `max_turns` + TTL；前缀注入限长 |
| 日志含敏感问句 | 合规风险 | 默认截断 query；可配置不落全文 |
| 全量 mode 误开 | 本机卡死 | config 默认 sample；full 需显式 |
| `sys.path` / `config` 撞名 | import 错模块 | 对齐 10 bootstrap 顺序 |

---

## 本周执行顺序（建议）

> 每完成一小阶段：**勾选 checklist → 填写完成/实现说明 → 补齐对应 notebook C* → 再进下一阶段**。

1. **阶段 0** 骨架 + bootstrap + notebook C0 / C0.5  
2. **阶段 1** 统一响应 / 错误码 / 异常(含 422→1001) / 日志 / `/health`(+`/ready`) + C1  
3. **阶段 2** `rag_service`（挂 10 `from_mode`）+ `session_store` + C2  
4. **阶段 3** 同步 `POST /qa` + 调用日志 + C3  
5. **阶段 4** SSE **伪流式** `/qa/stream` + C4  
6. **阶段 4.5** 全量 Dataset + Ollama 真跑 + 报告图（C4.5）  
7. **阶段 5** 交付收尾（README / docs 报告 / notebook 复核）✅

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-07-23 | 创建阶段 11 `schedule.md`，对齐任务书与 08/10 流水线，待启动实施 |
| 2026-07-23 | **计划修订（习惯层）**：notebook 改为贯穿式（对齐 09/10）；原「阶段 5=联调 Notebook 与交付」改为「交付收尾」；各小阶段预留完成说明 / 实现说明 |
| 2026-07-23 | **计划修订（内容层）**：伪流式定稿；会话 Store+可选 query 前缀；`top_k` 映射说明；去掉 per-request mode/stream；422→1001；勿挂 09 评估主路径；建议 `/ready`；字段映射对齐 10 `run` 返回值 |
| 2026-07-24 | **阶段 0 完成**：目录骨架、`config`/`bootstrap`/`main`/`probe`、`run_api.py`、notebook C0/C0.5；pytest **5 passed**；默认 `retrieval_mode=sample` |
| 2026-07-24 | **阶段 1 完成**：ResponseModel/ErrorCode/全局异常(422→1001)/中间件/日志、`/health` `/ready`、notebook C1；pytest **19 passed** |
| 2026-07-24 | **阶段 2 完成**：`RagService`（懒加载/mock/top_k/历史前缀/4001·4002）+ `MemorySessionStore`（TTL/max_turns/3002）+ deps；notebook C2；pytest **31 passed** |
| 2026-07-24 | **阶段 3 完成**：`POST /api/v1/qa` + `QACallLogger` + 会话两轮 + `GET /sessions/{id}`；notebook C3；pytest **35 passed** |
| 2026-07-25 | **阶段 4 完成**：伪 SSE `POST /api/v1/qa/stream`（meta→token*→done/error）；`sse_pseudo`；notebook C4；pytest **41 passed** |
| 2026-07-25 | **阶段 4.5 完成**：全量 live 骨架与首跑；报告图/JSON → `outputs/reports/`；notebook C4.5 |
| 2026-07-25 | **用户复跑 full live（最新）**：sync **179.53s** · 第二轮 **214.49s** · HTTP 探针 ≈126s · citation/format ok |
| 2026-07-25 | **阶段 5 完成**：`docs/服务化接口报告.md`；README ✅；C4.5 记录回填；`stage=5-done`；pytest **41 passed**；任务书结案 |
