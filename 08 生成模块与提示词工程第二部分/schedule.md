# 08 生成模块与提示词工程第二部分 — 执行计划

> **状态：✅ 已完成（阶段 0–6）**
>
> **本阶段范围（任务书）**：完成 **本地 LLM 集成（Ollama）** 与 **医学生成流水线（MedicalGenerationPipeline）**，串联 05→06→07 产出端到端 RAG 答案生成；**不包含** LangChain 封装与生产部署。
>
> **开发方式**：**单一 Notebook 贯穿全程**——`notebooks/medical-generation.ipynb` 在阶段 0 即创建，每完成一个开发阶段即在 notebook 中追加对应章节并跑通观测；**不**等到后期再集中写演示 notebook。
>
> **上游依赖**：
> - 07：`ContextAssembler`、`PromptStage` / `PROMPT_STAGES`
> - 06：`RetrievalPipeline`（`reranked` 候选 → 07 输入）
> - 05：`MedicalQueryEnhancer` / `EnhancedQuery`
> - 01：Ollama 服务与 `deepseek-r1:7b`（Windows 本地 LLM 验证）

---

## 任务书目标对照

| 任务书要求 | 本阶段交付 |
|------------|------------|
| `LLMGenerator`：Ollama 集成 | `src/llm_generator.py`：`model_name` / `base_url` / `timeout` |
| 初始化并测试连接 | `health_check()` / `ping()` |
| 单次生成（system + user + temperature + max_tokens） | `generate()` / `generate_json()` |
| JSON 输出解析与修复 | `extract_json()`：从模型文本中提取并补全 JSON |
| 批量生成 | `generate_batch()` |
| `MedicalGenerationPipeline` 端到端 | `src/generation_pipeline.py` |
| 上下文组装 | 调用 07 `ContextAssembler` |
| 证据评估（可选）→ 筛选上下文 | `evidence_evaluator` stage + doc_id/标题行过滤 |
| 答案草稿 → 批判审查（可选）→ 最终答案 | 三阶段 prompt 串联 |
| 后处理（引用、格式、免责声明） | `postprocess_answer()` / `_format_sources()` |
| 完整结果结构与指标 | `result` dict：`generation_metrics` / `intermediate_results` / `sources` |
| 测试完整流程 | notebook + 固定 query + log 导出 |

---

## 关键约束与设计决策（启动前）

| 项 | 决策 | 说明 |
|----|------|------|
| LLM 后端 | **Ollama HTTP API**（`127.0.0.1:11434`） | 与 01 阶段一致；`deepseek-r1:7b` 为默认模型 |
| 验证规模 | **样本库**（06 `mode="sample"`） | 与 06/07 开发期一致；全量检索切换留 RAG 上线前 |
| JSON 阶段 | evidence_evaluator / 部分中间步要求 JSON | 需 `extract_json()` 容错（模型常带 markdown 围栏） |
| 可选阶段 | evidence_evaluation、critical_review 可 `skip_*` 配置 | 任务书标注「可选」；默认开启，调试时可关 |
| 医学安全 | 最终答案必须带 **免责声明** | 后处理固定追加；critical_reviewer 强调不确定性 |
| 本阶段边界 | **不实现** LangChain LCEL、流式 UI、多模型路由 | 属后续 LangChain_RAG 或产品化 |
| **开发与观测** | **单一 notebook 增量追加** | `medical-generation.ipynb` 从阶段 0 起随进度扩展 C0→C7 |
| **阶段收尾** | **每阶段完成后同步文档再进入下一阶段** | 更新本 `schedule.md` + 根目录 `README.md` → 编写 git commit 指令方便提交 git 备份 |

---

## 开发与备份工作流（必遵）

每完成一个开发阶段（0→6），**在进入下一阶段编码前**按顺序执行：

| 步骤 | 动作 | 说明 |
|------|------|------|
| 1 | **Notebook 验证** | 运行本阶段对应 C* cell，确认输出与预期一致（实时观测进度） |
| 2 | **勾选本阶段 checklist** | 在本文件「分阶段执行」中将已完成项标为 `[x]` |
| 3 | **写阶段交付回顾**（可选一行） | 在对应阶段下补「交付回顾」表或「冒烟结果」一句 |
| 4 | **更新根目录 `README.md`** | 阶段一览状态、第八阶段进行中说明、更新记录表 |
| 5 | **git 提交** | 建议信息：`08: 完成阶段 N — <简述>`（含代码 + notebook + schedule + README） |

> **原则**：notebook 是开发期的**主观测面**；`schedule.md` / `README.md` 是**可提交的进度快照**，与 notebook 章节进度对齐。

### Notebook 章节与开发阶段对照（增量追加）

| 开发阶段 | Notebook 章节 | 观测内容 | 状态 |
|----------|---------------|----------|------|
| **0** 环境与骨架 | **C0** 前置：路径、`sys.path`、Ollama 配置 | 目录就绪、上游 05/06/07 可 import | ✅ |
| **1** LLMGenerator | **C1** Ollama 健康检查 + 单条 `generate()` | 连通性、温度/token 参数 | ✅ |
| **2** JSON 工具 | **C2** `extract_json` / `repair_json` 演示 | 围栏剥离、残缺 JSON 修复 | ✅ |
| **3** Pipeline 主流程 | **C3** 06→07 联调（样本或离线 JSON） | 检索 + 组装中间产物 | ✅ |
| **3**（续） | **C4** 最小路径 `run()`（跳过 eval/review） | 首条端到端答案（草稿+后处理） | ✅ |
| **3**（续） | **C5** 完整 pipeline（含 optional stages） | 四步 Prompt 串联、`result` 结构 | ✅ |
| **4** 后处理 | **C6** `sources`、引用 `[1][2]`、免责声明 | 与 `answer` 对齐的可视化 | ✅ |
| **5** CLI 评测 | **C7** 批量固定 query + 导出 `generation_eval.json` | 指标 log、多样例快照 | ✅ |
| **6** 测试与交付 | notebook **C7** 复跑 + `pytest tests/` | 回归全绿后 README 定稿 | ✅ |

> 阶段 3 子步骤（证据评估筛选、审查串联等）**进展到该步时再在 C4/C5 与 checklist 中细化**，启动前不展开。

---

## Windows Ollama 环境（方式 A，本机采用）

> 对照 01 阶段 Mac：`brew install` + `./start_ollama.sh` + 工程内 `ollama_models/`。  
> **Win 方式 A** 使用官方桌面版，模型默认在 `%USERPROFILE%\.ollama\models`，API 仍为 `http://127.0.0.1:11434`。

### 首次安装与拉模型（一次性）

| 步骤 | 操作 |
|------|------|
| 1 安装 | [ollama.com/download](https://ollama.com/download) → Windows 安装包 → 安装完成 |
| 2 启动服务 | 开始菜单打开 **Ollama**，或确认托盘区有 Ollama 图标（即后台监听 `11434`） |
| 3 拉取模型 | 在 **新开** PowerShell 中执行（见下方「PATH 未生效」） |
| 4 验证 | `ollama list` 含 `deepseek-r1:7b`，或 notebook **C0 探测 cell** 显示 `Probe OK: True` |

**本机默认模型**：`deepseek-r1:7b`（与 01 / `bootstrap.py` 一致）

### 日常启动（每次开发前）

方式 A **无需** `ollama serve` 常开窗口：

1. 确认托盘有 Ollama 图标；若无 → 开始菜单打开 **Ollama**
2. 打开 notebook（内核 `med-rag-verify`），运行 **C0 探测 cell**
3. 若 `Probe OK: False` 且提示缺模型 → 执行一次 `ollama pull deepseek-r1:7b`（或完整路径，见下）

### 故障：`ollama` 无法识别（CommandNotFoundException）

**原因**：Ollama 已安装，但当前 PowerShell **未加载** 安装程序写入的用户 PATH（常见于安装后未关终端、或 Cursor 内置终端早于安装启动）。

**本机实测**（2026-06-29）：

| 项 | 结果 |
|----|------|
| 可执行文件 | `%LOCALAPPDATA%\Programs\Ollama\ollama.exe` ✅ 存在 |
| `Get-Command ollama` | ❌ 找不到 |
| 版本 | `ollama version is 0.31.1`（用完整路径可执行） |

**处理（任选其一）**：

```powershell
# A) 当前窗口临时加入 PATH（推荐，装好后新开 PowerShell 往往已自带）
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
ollama pull deepseek-r1:7b
ollama list
```

```powershell
# B) 不依赖 PATH，直接用完整路径拉模型
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull deepseek-r1:7b
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
```

```powershell
# C) 彻底刷新环境：关闭所有 PowerShell / Cursor 终端 → 重新打开 → 再试 ollama pull
```

仍失败时：设置 → 系统 → 关于 → 高级系统设置 → 环境变量 → 用户 `Path` 中应含 `%LOCALAPPDATA%\Programs\Ollama`。

### 其他常见报错

| 现象 | 处理 |
|------|------|
| `connection refused` / `WinError 10061` | 托盘/开始菜单启动 Ollama |
| 服务可达但无 `deepseek-r1:7b` | `ollama pull deepseek-r1:7b`（或完整路径） |
| `ollama pull` 很慢 | 换网络；约 4.7GB |
| API `thinking` 过长超时 | HTTP payload 设 `think: false`；`max_tokens` 建议 ≥512（deepseek-r1） |

### 与 08 代码的对应

| 配置 | 值 |
|------|-----|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434`（`src/bootstrap.py`） |
| `OLLAMA_MODEL` | `deepseek-r1:7b` |
| 探测 | notebook C0 → `GET /api/tags` |

---

## 端到端数据流

```
用户 query（英文）
    ↓ 05 MedicalQueryEnhancer → EnhancedQuery
    ↓ 06 RetrievalPipeline → reranked 候选 list[dict]
    ↓ 07 ContextAssembler → { context_text, metadata, selected_chunks }
    ↓ 07 PROMPT_STAGES["evidence_evaluator"] → LLMGenerator（可选 JSON）
    ↓ 按评估结果筛选 selected_chunks（doc_id / 标题行）
    ↓ PROMPT_STAGES["answer_generator"] → draft_answer
    ↓ PROMPT_STAGES["critical_reviewer"] → review_feedback（可选）
    ↓ PROMPT_STAGES["final_assembler"] 或 草稿直出 → final_answer
    ↓ postprocess：引用标记 + 格式 + disclaimer
result { query, answer, context_metadata, generation_metrics, intermediate_results, sources, timestamp }
```

---

## 模块设计

### 目录结构（规划）

```text
08 生成模块与提示词工程第二部分/
├── 任务.txt
├── schedule.md                      # 本文件
├── requirements.txt                 # ollama 客户端 / httpx 等
├── src/
│   ├── __init__.py
│   ├── llm_generator.py             # LLMGenerator（Ollama）
│   ├── json_utils.py                # extract_json / repair_json
│   ├── generation_pipeline.py       # MedicalGenerationPipeline
│   └── postprocess.py               # 引用、免责声明、sources 格式化
├── notebooks/
│   └── medical-generation.ipynb     # C0 起随阶段增量：贯穿全程的主观测 notebook
├── scripts/
│   └── run_generation_eval.py       # CLI：批量 query + log 导出
├── tests/
│   ├── test_llm_generator.py        # mock Ollama 响应
│   ├── test_json_utils.py
│   └── test_generation_pipeline.py  # 离线 mock 全链路
└── outputs/
    ├── logs/                        # 每次生成的指标 log（.gitkeep）
    └── samples/
        └── generation_eval.json       # 固定 query 结果快照
```

### 核心 API（草案）

```python
class LLMGenerator:
  def __init__(self, model_name: str, base_url: str, timeout: float = 120.0): ...
  def health_check(self) -> bool: ...
  def generate(
      self,
      prompt: str,
      *,
      system_prompt: str | None = None,
      temperature: float = 0.2,
      max_tokens: int = 1024,
      json_mode: bool = False,
  ) -> str: ...
  def generate_batch(self, requests: list[dict]) -> list[str]: ...


class MedicalGenerationPipeline:
  def __init__(
      self,
      retrieval_pipeline,      # 06
      context_assembler,       # 07
      llm_generator,           # 08
      *,
      skip_evidence_eval: bool = False,
      skip_critical_review: bool = False,
  ): ...

  def run(self, query: str) -> dict:
      """返回任务书 result 结构（含 metrics / intermediates / sources）。"""
```

### 任务书 result 结构对照

| 字段 | 来源 |
|------|------|
| `query` | 原始用户输入 |
| `answer` | 后处理后的最终文本 |
| `context_metadata` | 07 `assemble()` 的 `metadata` |
| `generation_metrics.total_time_seconds` | `time.perf_counter()` 差值 |
| `generation_metrics.stage_times` | 各 stage 耗时 dict |
| `generation_metrics.token_counts` | 估算或 Ollama 返回的 prompt/eval 计数 |
| `generation_metrics.stage_success` | 各 stage 是否成功（含 JSON 解析） |
| `intermediate_results.evidence_evaluation` | evaluator 原始/解析 JSON |
| `intermediate_results.draft_answer` | answer_generator 输出 |
| `intermediate_results.review_feedback` | critical_reviewer 输出 |
| `sources` | `_format_sources(selected_chunks)` |
| `timestamp` | `time.strftime("%Y-%m-%d %H:%M:%S")` |

---

## 分阶段执行

### 阶段 0：环境与骨架 ✅

**阶段 0 完成说明**

- 做什么：把“施工现场”先搭好（目录、依赖、notebook、路径导入、Ollama探测）。
- 目标：确保后续阶段写代码时，不再被环境问题卡住；C0 一跑就知道上游模块和 Ollama 是否在线。

**代码 / 目录**

- [x] 创建 `src/`、`notebooks/`、`scripts/`、`tests/`、`outputs/logs/`、`outputs/samples/`
- [x] `requirements.txt`：`httpx` 或 `ollama` Python SDK（二选一）→ 已选 **httpx**
- [x] 确认 Ollama 服务可访问（`http://127.0.0.1:11434`，模型 `deepseek-r1:7b`）→ **探测逻辑已实现**（notebook C0 续）；本机须启动 Ollama 后 Probe OK
- [x] `sys.path` 引用 05/06/07 `src`（不复制模块）→ 经 `src/bootstrap.py`；**勿**提前挂载 05（与 07 `models` 冲突）

**Notebook（本阶段即创建）**

- [x] 创建 `notebooks/medical-generation.ipynb`
- [x] **C0**：前置说明 + 路径解析 + 上游模块 import smoke + Ollama 配置常量 + `/api/tags` 探测

**阶段 0 实现说明（代码路径 / 函数 / 方法）**

| 产物 | 路径 | 说明 |
|------|------|------|
| 路径引导 | `src/bootstrap.py` | `bootstrap_paths()`、`OLLAMA_*` 常量；08>06>07 优先级 |
| 依赖 | `requirements.txt` | `httpx>=0.27.0` |
| 演示 notebook | `notebooks/medical-generation.ipynb` | C0 import smoke + Ollama probe（软失败提示） |
| 目录骨架 | `src/`、`scripts/`、`tests/`、`outputs/` | 含 `.gitkeep` |

**冒烟结果**：`bootstrap_paths` + import `RetrievalPipeline` / `ContextAssembler` / `PROMPT_STAGES` ✅；Ollama 探测在本环境连接被拒（服务未启动），C0 已打印启动指引，**阶段 1 前须重跑 C0 使 Probe OK**。

**阶段收尾** → 更新 `schedule.md` / `README.md` → git 提交

---

### 阶段 1：LLMGenerator（Ollama 集成） ✅

**阶段 1 完成说明**

- 做什么：封装一个稳定的“模型调用器”，统一管理 `health_check`、单次生成、批量生成和 JSON 生成入口。
- 目标：以后所有生成步骤都通过同一个类调用 Ollama，避免在 pipeline 里散落 HTTP 细节。
- `health_check` 只探测 `GET /api/tags` 是否连通，不生成答案；C1 显示 True 才值得跑 `generate()`。
**代码**

- [x] `LLMGenerator.__init__(model_name, base_url, timeout)`
- [x] `health_check()`：GET `/api/tags` 或等价探测（`ping()` 别名）
- [x] `generate()`：
  - [x] 组装 system + user prompt（`/api/chat`）
  - [x] 支持 `temperature`、`max_tokens`（`num_predict`）
  - [x] 默认 `think=False`（deepseek-r1，对齐 01 阶段）
- [x] `generate_json()`：JSON 约束 + `extract_json()`（`json_utils` 基础版，阶段 2 扩展）
- [x] `generate_batch()`：顺序批量
- [x] 单元测试：mock HTTP，`tests/test_llm_generator.py` 4 项

**Notebook**

- [x] **C1**：`health_check()` + 单条 `generate()` smoke

**阶段 1 实现说明（代码路径 / 函数 / 方法）**

| 产物 | 路径 | 说明 |
|------|------|------|
| 生成器 | `src/llm_generator.py` | `/api/chat`、`think=False`、context manager |
| JSON 基础 | `src/json_utils.py` | `extract_json`（阶段 2 扩展 `repair_json`） |
| 单测 | `tests/test_llm_generator.py` | 4 passed |
| Notebook | C1 | health + 单条医学问句生成 |

**阶段收尾** → 更新 `schedule.md` / `README.md` → git 提交

---

### 阶段 2：JSON 提取与修复 ✅

**阶段 2 完成说明**

- 做什么：把模型返回的“可能不规范 JSON 文本”尽量修成可解析结构，并定义证据评估最小 schema。
- 目标：即使模型输出带围栏、尾逗号、缺括号，也尽量解析成功；失败时 `evaluation=None` 不筛选 chunk，主流程继续。
**代码**

- [x] `extract_json(text) -> dict | None`：剥离 ` ```json ` 围栏；失败时走 `repair_json`
- [x] `repair_json(text) -> str`：尾逗号、缺 `}`/`]`、未闭合引号
- [x] 证据评估 schema（最小字段）：
  - [x] `relevant_chunk_ids: list[str]`
  - [x] `excluded_chunk_ids: list[str]`
  - [x] `notes: str`
  - [x] `parse_evidence_evaluation` / `normalize_evidence_evaluation`
- [x] 解析失败降级：`filter_chunks_by_evidence_eval(..., None)` → 原样返回全部 chunks

**Notebook**

- [x] **C2**：围栏 + 残缺修复 + mock `generate_json` 输出 + 筛选降级演示

**阶段 2 实现说明（代码路径 / 函数 / 方法）**

| 产物 | 路径 | 说明 |
|------|------|------|
| JSON 工具 | `src/json_utils.py` | extract / repair / evidence eval / chunk 筛选 |
| 单测 | `tests/test_json_utils.py` | 8 项 |
| Notebook | C2 | mock 联调，不额外消耗 LLM |

**阶段收尾** → 更新 `schedule.md` / `README.md` → git 提交

---

### 阶段 3：MedicalGenerationPipeline 主流程 ✅

**阶段 3 完成说明**

- 做什么：把 06 检索、07 组装、08 生成串成一个 `run(query)` 端到端流程。
- 目标：输入一个问题就得到统一的 `result`（答案、中间产物、耗时、阶段成功率、sources）。

**代码**

- [x] 初始化：注入 06 retrieval、07 assembler、08 llm
- [x] 上下文组装 →（可选）证据评估 → 答案草稿 →（可选）批判审查 → 终稿
- [x] 组装 `result` dict（对齐任务书字段）；记录 `stage_times` / `stage_success`
- [x] 证据评估失败降级：不筛选 chunks，继续主流程
- [x] 基础后处理：免责声明 + 引用编号 + `sources` 对齐（阶段 4 深化）

**Notebook**

- [x] **C3**：06 sample 离线样例 → 07 组装，展示 `context_text` / metadata
- [x] **C4**：最小路径 `MedicalGenerationPipeline.run()`（`skip_evidence_eval=True`, `skip_critical_review=True`）
- [x] **C5**：完整 pipeline + optional stages 开关对比

**阶段 3 实现说明（代码路径 / 函数 / 方法）**

| 产物 | 路径 | 说明 |
|------|------|------|
| 生成主流程 | `src/generation_pipeline.py` | `MedicalGenerationPipeline.run()` 端到端串联 |
| 单测 | `tests/test_generation_pipeline.py` | 2 项：最小路径 / 完整路径 |
| Notebook | C3–C5 | 离线检索输入 + 最小/完整路径对比 |
| 测试汇总 | `pytest tests/ -v` | 14 项全绿 |

**阶段收尾** → 更新 `schedule.md` / `README.md` → git 提交

---

### 阶段 4：后处理与 sources 格式化 ✅

**阶段 4 完成说明**

- 做什么：把“模型原始答案”整理成可交付文本（引用编号、来源列表、免责声明）。
- 目标：答案对用户可读、可追溯，引用 `[1][2]` 与 `sources` 列表一一对应。

**代码**

- [x] `format_sources(chunks) -> list[dict]`：`chunk_id`、`source_title`、`doc_id`、`relevance_score`
- [x] 答案内引用标记与 `sources` 列表序号对齐
- [x] 固定免责声明文案（英文，与 PMC 英文语料一致）
- [x] `postprocess_answer()` 统一入口

**Notebook**

- [x] **C6**：展示 `answer` 内 `[1][2]`、`sources` 表、免责声明段落

**阶段 4 实现说明（代码路径 / 函数 / 方法）**

| 产物 | 路径 | 说明 |
|------|------|------|
| 后处理模块 | `src/postprocess.py` | `format_sources` + `postprocess_answer` + 免责声明常量 |
| 流水线对接 | `src/generation_pipeline.py` | 改用 `postprocess.py` 统一后处理 |
| 单测 | `tests/test_postprocess.py` | 3 项（引用/来源/免责声明） |
| Notebook | C6 | 展示引用标记、Sources 区块、免责声明 |
| 测试汇总 | `pytest tests/ -v` | 17 项全绿 |

**阶段收尾** → 更新 `schedule.md` / `README.md` → git 提交

---

### 阶段 5：CLI 评测与批量快照 ✅

**阶段 5 完成说明**

- 做什么：把单次 notebook 演示扩展成“批量 query 自动跑 + 自动记录指标”。
- 目标：沉淀 `generation_eval.json` 快照，供 09 评估与跨阶段对比；默认走 06 样本库离线检索。

**代码**

- [x] `scripts/run_generation_eval.py`：批量跑固定 query 列表 + 写 `outputs/logs/`

**Notebook**

- [x] **C7**：跑 ≥4 条固定 query（见下表），展示 `generation_metrics`，导出 `outputs/samples/generation_eval.json`

**阶段 5 实现说明（代码路径 / 函数 / 方法）**

| 产物 | 路径 | 说明 |
|------|------|------|
| 批量评测脚本 | `scripts/run_generation_eval.py` | 默认 4 条 query，离线检索样例驱动 |
| 评测快照 | `outputs/samples/generation_eval.json` | 最新可复现结果 |
| 评测日志 | `outputs/logs/generation_eval_*.json` | 带时间戳历史记录 |
| Notebook | C7 | 脚本触发 + 结果摘要 |
| 运行结果 | CLI 实测 | 4/4 query 跑通，全部生成成功 |

**阶段收尾** → 更新 `schedule.md` / `README.md` → git 提交

---

### 阶段 6：测试与交付 ✅

**阶段 6 完成说明**

- 做什么：补齐测试、复跑关键样例、整理报告和 README，完成最终交付收口。
- 目标：链路稳定可回归（pytest 17 passed），文档可验收；`generation_eval.json` 成为 09 上游。

**代码**

- [x] `test_json_utils.py`：围栏剥离、残缺 JSON 修复
- [x] `test_generation_pipeline.py`：mock LLM 全链路（无 Ollama 也可 CI）
- [x] 固定测试 query log 关键指标（与 C7 快照一致或复跑）

**文档**

- [x] `docs/医学生成流水线报告.md`
- [x] 根目录 `README.md` 第八阶段**完成**定稿（阶段一览 ✅、完成总结、更新记录）

**Notebook**

- [x] **C7** 全量复跑确认；追加 pytest 结果摘要 cell（C7 复跑确认）

**阶段 6 实现说明（代码路径 / 函数 / 方法）**

| 产物 | 路径 | 说明 |
|------|------|------|
| 正式报告 | `docs/医学生成流水线报告.md` | 阶段 0–6 总结与交付说明 |
| 回归测试 | `pytest tests/ -v` | 17 项全绿 |
| Notebook 收尾 | C7 + C7（复跑确认） | 批量评测 + pytest 摘要 |
| README 定稿 | 根目录 `README.md` | 第八阶段状态与产出同步 |

**阶段收尾** → 最终 git 提交

---

## 验证用例（首批）

| # | 输入 query（英文） | 关注点 |
|---|-------------------|--------|
| 1 | `What is the treatment for MI?` | 缩写扩展 + 证据引用 + 免责声明 |
| 2 | `metformin cardiovascular effects` | 多 chunk 组装 + sources 对齐 |
| 3 | `papers on malaria after 2015` | 证据评估筛选是否生效 |
| 4 | `warfarin atrial fibrillation elderly` | 批判审查是否提示出血风险等 |

**每次生成需 log 的指标**（任务书要求）：

| 指标 | 说明 |
|------|------|
| `total_time_seconds` | 端到端耗时 |
| `stage_times` | assemble / eval / draft / review / final / postprocess |
| `answer_length` | 最终答案字符数 |
| `chunks_selected` | 进入 prompt 的块数 |
| `stage_success` | 各阶段是否成功（尤其 JSON 解析） |
| `sources` | 引用来源列表 |

---

## 交付产物清单（预填）

| 产物 | 格式 | 路径 | Git |
|------|------|------|-----|
| Ollama 生成器 | Python | `src/llm_generator.py` | ✅ |
| JSON 工具 | Python | `src/json_utils.py` | ✅ |
| 医学生成流水线 | Python | `src/generation_pipeline.py` | ✅ |
| 后处理 | Python | `src/postprocess.py` | ✅ |
| 演示 notebook | `.ipynb` | `notebooks/medical-generation.ipynb` | ✅ |
| CLI 评测 | Python | `scripts/run_generation_eval.py` | ✅ |
| 评测样例 | JSON | `outputs/samples/generation_eval.json` | ✅ |
| 运行 log | JSONL/JSON | `outputs/logs/*.json` | ✅（小文件） |
| Ollama 模型权重 | — | 01 阶段已有 | ❌ |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Ollama 未启动 / 模型未拉取 | 流水线失败 | C0 健康检查；README 指向 01 启动说明 |
| deepseek-r1 输出冗长 / 带 `` | JSON 解析失败 | `extract_json` 容错；eval 阶段可 `skip` |
| 单次生成超时 | notebook 卡住 | `timeout` 可配；`max_tokens` 分 stage 限制 |
| 证据评估误删有效 chunk | 答案质量下降 | 解析失败则**不筛选**；仅按 id 白名单剔除 |
| 端到端耗时过长 | 调试效率低 | 开发期 `skip_critical_review=True`；样本库 + 少 chunk |

---

## 本周执行顺序（建议）

每个编号 = **开发 + notebook 对应章节跑通 + schedule/README 同步 + git 提交** 后再进入下一项。

1. **阶段 0**：目录骨架 + **创建 notebook C0**  
2. **阶段 1**：`LLMGenerator` + **notebook C1**（Ollama smoke）  
3. **阶段 2**：`json_utils` + **notebook C2**  
4. **阶段 3**：Pipeline 最小路径 + **notebook C3–C4**；再补 optional stages + **C5**  
5. **阶段 4**：后处理 + **notebook C6**  
6. **阶段 5**：CLI + **notebook C7** 批量快照  
7. **阶段 6**：pytest + 正式报告 + README 定稿  

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-06-28 | 创建阶段 08 `schedule.md`，对齐任务书与 05/06/07 接口，待启动实施 |
| 2026-06-29 | 调整开发方式：**notebook 贯穿全程**；每阶段收尾同步 `schedule.md` + `README.md`；创建 `medical-generation.ipynb` C0 骨架 |
| 2026-06-29 | **阶段 0 完成**：`bootstrap.py`、目录骨架、C0 import/Ollama 探测；进入阶段 1 |
| 2026-06-30 | **Win Ollama 方式 A**：`schedule.md` 记入全流程；本机 `ollama` CLI 未进 PATH，拉模型需完整路径或刷新终端 |
| 2026-07-01 | **阶段 1 完成**：`LLMGenerator` + `json_utils.extract_json` 基础版 + C1 + pytest 4 项 |
| 2026-07-01 | **阶段 2 完成**：`repair_json`、证据评估 schema、`filter_chunks_by_evidence_eval` + C2 + pytest 12 项 |
| 2026-07-01 | **阶段 3 完成**：`MedicalGenerationPipeline` + C3/C4/C5 + `test_generation_pipeline.py`，pytest 14 项 |
| 2026-07-01 | **阶段 4 完成**：`postprocess.py` + C6 + `test_postprocess.py`，pytest 17 项 |
| 2026-07-01 | **阶段 5 完成**：`run_generation_eval.py` + C7 + `generation_eval.json`/日志快照 |
| 2026-07-01 | **阶段 6 完成**：报告定稿 + C7 复跑 + pytest 摘要；阶段 08 收口完成 |
| 2026-07-02 | **阶段 6 文档完善**：补充 C0–C7 实测数据与任务书逐条验证；pytest 复跑仍为 17 passed |
