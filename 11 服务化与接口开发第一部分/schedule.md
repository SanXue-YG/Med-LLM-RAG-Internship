# 11 服务化与接口开发第一部分 — 执行计划

> **状态：🔄 待启动**
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

### Notebook 贯穿策略 ☐

> 对齐 09 / 10：`api-smoke.ipynb` **不是**收尾才补的演示章，而是**随各小阶段增量追加**的可视化成果与测试入口。

- [ ] 采用**单一 notebook 贯穿式开发**：`notebooks/api-smoke.ipynb`
- [ ] 每完成一个小阶段，立即补齐对应 C* 单元并保存输出，**不等到最后统一补**
- [ ] 阶段与单元映射：

| 小阶段 | Notebook | 作用 |
|--------|----------|------|
| 0 骨架 | C0 / C0.5 | 目录与依赖、`config` 加载、uvicorn / `app` 可 import；可选探活 |
| 1 统一响应 / 异常 / 健康 | C1 | `ResponseModel` 样例、错误码 1001 形态、`GET /health` |
| 2 RAG 服务 + 会话 | C2 | `rag_service.answer`（可 mock）+ `SessionStore` 增删查 |
| 3 同步问答 | C3 | `POST /api/v1/qa` 成功 / 参数错误 / 带 `session_id` 两轮 |
| 4 流式问答 | C4 | `POST /qa/stream`：meta → token → done（或 error） |
| 5 交付收尾 | （全量复核 C0–C4） | 与代码一致性检查；实跑 1–2 条 + 日志确认；**不新增演示章** |

> 每完成一小阶段工作流：**勾选 checklist → 填写完成说明 / 实现说明 → 补齐对应 notebook C* → 再进下一阶段**。

### 阶段 0：环境与骨架 ☐

- [ ] 创建目录结构（`app/`、`scripts/`、`tests/`、`notebooks/`、`outputs/logs/`）
- [ ] `requirements.txt`：`fastapi`、`uvicorn[standard]`、`pydantic`、`httpx`
- [ ] `app/config.py`：host/port、默认 `retrieval_mode=sample`、日志路径、`pipeline_backend=constrained10`
- [ ] `app/bootstrap.py`（或等价）：挂 10/08 `sys.path`，避免与 06/09 `config` 撞名（对齐 10）
- [ ] `scripts/run_api.py`：`uvicorn app.main:app --reload`
- [ ] Notebook **C0**：环境初始化 + import `app` / `config` + 依赖自检
- [ ] Notebook **C0.5**：Ollama 探活（`LLMGenerator.ping` 或 httpx）；确认 10 模块可 import（**不**强制冷启全量库）

**阶段 0 完成说明**

- （预留）搭好 11 工程骨架：目录、依赖、`config`、启动入口；贯穿式 notebook 建好 C0 / C0.5。
- （预留）此阶段**不**实现统一响应信封、**不**挂 RAG、**不**对外问答——只把「可启动的空壳服务」场地准备好。

**阶段 0 实现说明（代码路径 / 函数 / 方法）**

- （预留）`app/config.py` → …
- （预留）`scripts/run_api.py` → …
- （预留）`notebooks/api-smoke.ipynb` **C0 / C0.5** → …
- （预留）`requirements.txt` → …

### 阶段 1：统一响应、错误码、全局异常、日志、健康检查 ☐

- [ ] `ResponseModel` / `PageModel`
- [ ] `ErrorCode` 枚举（至少 1001 / 2001 / 3001 / 4001 + 内部 5000）
- [ ] `AppException(code, message, detail=None)`
- [ ] 全局 handler：`AppException` / `RequestValidationError`→**1001** / 未捕获→**5000**
- [ ] 中间件：生成 `request_id`、记录耗时、写入响应头 `X-Request-Id`
- [ ] 结构化日志（console + 可选文件）
- [ ] `GET /health` → `{ status: "ok", ollama?: bool }`（进程活；Ollama 可选探测）
- [ ] （建议）`GET /ready` → pipeline 是否已加载
- [ ] 单元测试：校验失败返回 **400 + code=1001** 形态；健康检查 200
- [ ] Notebook **C1**：构造 `ResponseModel` 成功/失败样例；`TestClient` 调 `/health`；故意触发校验错误看 1001 信封

**阶段 1 完成说明**

- （预留）本阶段相当于把「前台小票格式 + 拒单话术 + 探活灯」定下来：所有接口成功/失败长一个样，带 `request_id`。
- （预留）`/health` 可探活；全局异常不再把裸堆栈甩给客户端。
- （预留）此阶段**尚无**真实问答路由；焦点是契约与可观测性。

**阶段 1 实现说明（代码路径 / 函数 / 方法）**

- （预留）`app/schemas/response.py` → `ResponseModel` / `PageModel`
- （预留）`app/core/error_codes.py` → `ErrorCode`
- （预留）`app/core/exceptions.py` → `AppException` + handlers
- （预留）`app/core/middleware.py` / `logging.py` → …
- （预留）`app/api/health.py` → `GET /health`
- （预留）`tests/test_health.py` / `test_response_model.py` / `test_error_handlers.py`
- （预留）`notebooks/api-smoke.ipynb` **C1**

### 阶段 2：RAG 服务封装与会话存储 ☐

- [ ] `rag_service.py`：懒加载 / 单例持有 pipeline
  - [ ] 工厂：`ConstrainedGenerationPipeline.from_mode(config.retrieval_mode)`（默认 sample）
  - [ ] `answer(query, top_k=None, session_history=None) -> dict`
  - [ ] `top_k`：尽量写入 `retrieval_pipeline.top_k_final`；若不可达则截断返回 `sources[:top_k]` 并在 metrics 注明
  - [ ] `session_history`：MVP 可将最近轮次格式化为短前缀拼进 `effective_query`；**不**调用不存在的 `run(..., history=)`
  - [ ] 异常映射：`httpx`/连接/超时 → `4001`；其它流水线异常 → `4002`
- [ ] `session_store.py`：
  - [ ] `create()` / `get(session_id)` / `append(session_id, turn)`
  - [ ] TTL + `max_turns`（如 10）；过期策略写清（3002 vs 自动新建）
- [ ] Notebook **C2**：优先 **mock pipeline** 测封装；可选 sample 真跑 1 条；`SessionStore` create → append → get 演示

**阶段 2 完成说明**

- （预留）本阶段把「后厨叫号口」和「桌号档案」做出来：HTTP 层之后先调 `rag_service`，会话历史进内存 Store。
- （预留）Ollama / 流水线失败已映射到业务错误码；会话**至少**可存可取，注入生成采用轻量 query 前缀（不改 08/10）。
- （预留）此阶段**可不挂**正式 `/qa` 路由；notebook / 单测直接调 service 即可验收。

**阶段 2 实现说明（代码路径 / 函数 / 方法）**

- （预留）`app/services/rag_service.py` → `from_mode` 懒加载 / `answer` / `top_k` 映射 / 异常映射
- （预留）`app/services/session_store.py` → `create` / `get` / `append` + TTL / `max_turns`
- （预留）`app/deps.py` → Depends 单例
- （预留）相关单元测试（mock `run`）
- （预留）`notebooks/api-smoke.ipynb` **C2**

### 阶段 3：同步问答接口 ☐

- [ ] `POST /api/v1/qa`（同步 `def` 或 executor，避免堵事件循环）
- [ ] 参数校验：`query` 非空且 `≤ max_length`；`top_k ∈ [1, 20]` → **1001**
- [ ] 若传 `session_id`：关联 Store；若无则新建并回传
- [ ] 成功：`ResponseModel(code=0, data=QAResponseData, ...)`；透出 `constraint_checks`（走 10 时）
- [ ] `qa_logger`：写 `request_id`、耗时、状态、query 摘要（注意脱敏）
- [ ] TestClient：mock `rag_service` 测参数错误与成功路径
- [ ] Notebook **C3**：`POST /qa` 合法 query；空 query / 非法 `top_k` → 1001；带 `session_id` 连问两轮（断言 Store 有两轮）；确认日志行

**阶段 3 完成说明**

- （预留）本阶段打通「同步点餐」：外部客户端一次 `POST` 拿齐 `answer` + `sources`（及 `constraint_checks`）。
- （预留）参数校验、会话关联、调用日志齐备；mock 单测覆盖成功与 1001 路径。
- （预留）验收口径：验证用例 #5「第二轮能读到历史」= **Store 有记录**（及可选 query 前缀注入）；不要求 08/10 原生多轮 API。

**阶段 3 实现说明（代码路径 / 函数 / 方法）**

- （预留）`app/api/qa.py` → `POST /api/v1/qa`
- （预留）`app/schemas/qa.py` → `QARequest` / `QAResponseData`
- （预留）`app/services/qa_logger.py` → 落盘 JSONL
- （预留）`tests/test_qa_api.py`
- （预留）`notebooks/api-smoke.ipynb` **C3**

### 阶段 4：流式问答接口 ☐

- [ ] `POST /api/v1/qa/stream` → SSE（`StreamingResponse` / `sse-starlette` 任选）
- [ ] 事件约定：
  - [ ] `event: meta` — request_id / session_id / `stream_mode: "pseudo"`（或后续 `"token"`）
  - [ ] `event: token` — 增量文本
  - [ ] `event: done` — 完整 answer / sources / metrics / constraint_checks?
  - [ ] `event: error` — 标准错误码 JSON（与同步信封字段对齐）
- [ ] **MVP 实现定稿：伪流式**
  - [ ] 调用与同步相同的 `rag_service.answer`（完整约束闭环）
  - [ ] 将 `answer` 按句或固定窗口切分推送 `token`
  - [ ] 文档 / notebook / OpenAPI 标明：非 Ollama token 级真流式
- [ ] （可选后续，本周不阻塞）探测/扩展 `LLMGenerator` 真流式；若做，须单独说明与约束重试的冲突
- [ ] 结束时写调用日志（总耗时与状态）
- [ ] Notebook **C4**：消费 SSE；展示 meta → token* → done；异常走 error；打印 `stream_mode`

**阶段 4 完成说明**

- （预留）本阶段打通「边做边上」的 **API 形态**：SSE 事件约定清晰；MVP 为伪流式，验收不依赖改 08。
- （预留）流式结束同样写调用日志；`done` 中 sources/metrics 与同步路径一致（因同源 `answer()`）。

**阶段 4 实现说明（代码路径 / 函数 / 方法）**

- （预留）`app/api/qa.py` → `POST /api/v1/qa/stream`
- （预留）伪流式分块工具函数 → …
- （预留）相关测试（可用 httpx 流式或拆事件解析）
- （预留）`notebooks/api-smoke.ipynb` **C4**

### 阶段 5：交付收尾 ☐

> Notebook 演示已拆入阶段 0–4；本阶段只做**打包与文档对齐**，不再单独堆演示单元。

- [ ] Notebook 全量复核：检查 C0–C4 与各阶段代码一致、输出可复现
- [ ] 用 08/10 熟悉 query（如 `metformin cardiovascular effects`）实跑 1–2 条（可在已有 C3/C4 复跑）
- [ ] 确认日志文件有 `request_id` / latency / status
- [ ] 更新根目录 `README.md` 阶段 11 条目（完成后）
- [ ] （可选）`docs/服务化接口报告.md` 或 OpenAPI（`/docs`）截图说明
- [ ] 勾选本 schedule 全部完成项；进度记录补全收尾日期

**阶段 5 完成说明**

- （预留）交付打包：README / 可选正式报告与 OpenAPI 说明对齐；C0–C4 复核通过。
- （预留）像 10 的阶段 6：不再加新接口能力，只做归档与对外说明。

**阶段 5 实现说明（代码路径 / 函数 / 方法）**

- （预留）根目录 `README.md` 阶段 11 条目
- （预留）可选 `docs/服务化接口报告.md`
- （预留）`notebooks/api-smoke.ipynb` C0–C4 全量复核记录
- （预留）本文件状态栏 → ✅

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
| API smoke notebook（贯穿 C0–C4） | `.ipynb` | `notebooks/api-smoke.ipynb` | ✅ |
| 单元测试 | Python | `tests/` | ✅ |
| 调用日志样例 | JSONL | `outputs/logs/qa_calls.jsonl` | ✅（可脱敏） |
| OpenAPI | 自动 | `/docs`（Swagger） | — |

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
6. **阶段 5** 交付收尾（README / 可选 docs / notebook 全量复核）

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-07-23 | 创建阶段 11 `schedule.md`，对齐任务书与 08/10 流水线，待启动实施 |
| 2026-07-23 | **计划修订（习惯层）**：notebook 改为贯穿式（对齐 09/10）；原「阶段 5=联调 Notebook 与交付」改为「交付收尾」；各小阶段预留完成说明 / 实现说明 |
| 2026-07-23 | **计划修订（内容层）**：伪流式定稿；会话 Store+可选 query 前缀；`top_k` 映射说明；去掉 per-request mode/stream；422→1001；勿挂 09 评估主路径；建议 `/ready`；字段映射对齐 10 `run` 返回值 |
