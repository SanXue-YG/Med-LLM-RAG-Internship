# 医学 RAG 实习工程 — 总说明

基于 PMC 开放获取文献（`oa_comm`）的本地 LLM + RAG 可行性验证与数据评估项目。工程按阶段拆分目录，每阶段有独立任务书、计划、依赖与 Jupyter 入口。

> **给老师 / 审阅者**：各阶段**任务原文**见各目录下 `任务.txt`；**执行计划与进度**见各目录 `schedule.md`；**正式分析结论**见各阶段 `docs/`（02：`RAG数据分析与设计说明.md`；03：`文档分割处理报告.md`；04：`向量化与索引报告.md`；05：`查询理解与增强报告.md`；06：`检索流水线报告.md`；07：`上下文组装与提示工程报告.md`；08：`医学生成流水线报告.md`；09：`答案评估与缓存报告.md`）。

---

## README 结构说明

> 本表供快速定位与后续维护 README 时使用；**新增阶段请按相同板块更新对应章节**。

| 章节 | 作用 | 更新时机 |
|------|------|----------|
| **文件目录结构** | 仓库顶层目录树与各阶段文件夹 | 新增/重命名阶段目录时 |
| **阶段一览** | 各阶段状态、任务书、计划、notebook、依赖的一览表 | 每阶段启动或收尾时 |
| **各阶段完成总结** | 各阶段任务、项目位置、关键结果、产出索引（**不写冗长实现细节**） | 阶段收尾时追加/修订对应小节 |
| **Python 环境与依赖** | Conda 环境、分阶段 `requirements.txt`、根目录一键依赖 | 某阶段引入新包时 |
| **本地部署指南** | 从 GitHub 克隆后的搭建步骤；`.gitignore` 与未上传大文件说明 | 数据路径或 ignore 规则变化时 |
| **各阶段交付物速查** | 精炼成果、⚠️ 边界、API、**schedule 后续开发注意** | 阶段收尾；schedule 有新增注意事项时 |
| **笔记目录** | 个人学习 Q&A（非正式交付） | 写新笔记时 |
| **更新记录** | 按时间线的变更日志；**当前阶段条目加粗**，阶段结束后整合为普通条目 | 阶段进行中实时更新 |

**阅读顺序建议**：新人 → 阶段一览 → 本地部署指南 → 当前阶段交付物速查 → 对应 `schedule.md`。

---

## 文件目录结构

```text
谷歌/
├── README.md                 # 本文件（项目总说明）
├── requirements.txt          # 依赖安装清单（说明）；一键安装见 install_all_requirements.ps1
├── install_all_requirements.ps1  # 按阶段顺序 pip install（推荐）
├── .gitignore                # Git 忽略规则
├── setup_windows_env.ps1     # Windows 环境一键配置脚本
├── setup_stage04_gpu.ps1     # 04 全量向量化：CUDA 版 PyTorch 补充安装
├── 01 验证模型/              # 阶段 1：本地 LLM + PMC 数据源验证（✅）
├── 02 数据处理/              # 阶段 2：数据加载与评估（✅）
├── 03 文档解析与分割/        # 阶段 3：文本分割（✅）
├── 04 向量化与索引构建/      # 阶段 4：嵌入 + ChromaDB 索引（✅ 全量完成）
├── 05 检索系统开发第一部分/  # 阶段 5：查询理解与增强（✅）
├── 06 检索系统开发第二部分/  # 阶段 6：多路检索 + 融合 + 重排序（✅）
├── 07 生成模块与提示词工程第一部分/  # 阶段 7：上下文组装 + Prompt 模板（✅）
├── 08 生成模块与提示词工程第二部分/  # 阶段 8：Ollama 生成 + 端到端流水线（✅）
├── 09 生成答案评估，缓存策略与批量处理/  # 阶段 9：评估 + 缓存 + 批量（✅）
├── ** LangChain_RAG/         # RAG 系统开发（待定）
└── 笔记/                     # 个人学习笔记
```

---

## 阶段一览

| 阶段 | 目录 | 状态 | 任务书 | 计划 | 运行入口（Jupyter） | 依赖 |
|------|------|------|--------|------|---------------------|------|
| **01** 验证模型 | [`01 验证模型/`](01%20验证模型/) | ✅ 已完成 | [`任务.txt`](01%20验证模型/任务.txt) | [`schedule.md`](01%20验证模型/schedule.md) | [`med-LLM-RAG.ipynb`](01%20验证模型/med-LLM-RAG.ipynb) | [`requirements.txt`](01%20验证模型/requirements.txt) |
| **02** 数据处理 | [`02 数据处理/`](02%20数据处理/) | ✅ 已完成 | [`任务.txt`](02%20数据处理/任务.txt) | [`schedule.md`](02%20数据处理/schedule.md) | [`partA.ipynb`](02%20数据处理/notebooks/med-data-EDA-partA.ipynb)（验证）· [`partB.ipynb`](02%20数据处理/notebooks/med-data-EDA-partB.ipynb)（全量） | [`requirements.txt`](02%20数据处理/requirements.txt) |
| **03** 文档解析与分割 | [`03 文档解析与分割/`](03%20文档解析与分割/) | ✅ 已完成 | [`任务.txt`](03%20文档解析与分割/任务.txt) | [`schedule.md`](03%20文档解析与分割/schedule.md) | [`doc-chunking.ipynb`](03%20文档解析与分割/notebooks/doc-chunking.ipynb)（验证）· [`full.ipynb`](03%20文档解析与分割/notebooks/doc-chunking-full.ipynb)（全量） | *复用 02* · [`requirements.txt`](03%20文档解析与分割/requirements.txt)（说明） |
| **04** 向量化与索引构建 | [`04 向量化与索引构建/`](04%20向量化与索引构建/) | ✅ **已完成** | [`任务.txt`](04%20向量化与索引构建/任务.txt) | [`schedule.md`](04%20向量化与索引构建/schedule.md) | [`vectorize-index.ipynb`](04%20向量化与索引构建/notebooks/vectorize-index.ipynb)（验证）· [`full.ipynb`](04%20向量化与索引构建/notebooks/vectorize-index-full.ipynb)（全量） | [`requirements.txt`](04%20向量化与索引构建/requirements.txt) |
| **05** 检索系统开发第一部分 | [`05 检索系统开发第一部分/`](05%20检索系统开发第一部分/) | ✅ **已完成** | [`任务.txt`](05%20检索系统开发第一部分/任务.txt) | [`schedule.md`](05%20检索系统开发第一部分/schedule.md) | [`query-enhancement.ipynb`](05%20检索系统开发第一部分/notebooks/query-enhancement.ipynb) | [`requirements.txt`](05%20检索系统开发第一部分/requirements.txt) |
| **06** 检索系统开发第二部分 | [`06 检索系统开发第二部分/`](06%20检索系统开发第二部分/) | ✅ **已完成** | [`任务.txt`](06%20检索系统开发第二部分/任务.txt) | [`schedule.md`](06%20检索系统开发第二部分/schedule.md) | [`retrieval-pipeline.ipynb`](06%20检索系统开发第二部分/notebooks/retrieval-pipeline.ipynb) | [`requirements.txt`](06%20检索系统开发第二部分/requirements.txt) |
| **07** 生成模块与提示词工程第一部分 | [`07 生成模块与提示词工程第一部分/`](07%20生成模块与提示词工程第一部分/) | ✅ **已完成**（0–5） | [`任务.txt`](07%20生成模块与提示词工程第一部分/任务.txt) | [`schedule.md`](07%20生成模块与提示词工程第一部分/schedule.md) | [`generation-prompting.ipynb`](07%20生成模块与提示词工程第一部分/notebooks/generation-prompting.ipynb) | [`requirements.txt`](07%20生成模块与提示词工程第一部分/requirements.txt) |
| **08** 生成模块与提示词工程第二部分 | [`08 生成模块与提示词工程第二部分/`](08%20生成模块与提示词工程第二部分/) | ✅ **已完成**（0–6） | [`任务.txt`](08%20生成模块与提示词工程第二部分/任务.txt) | [`schedule.md`](08%20生成模块与提示词工程第二部分/schedule.md) | [`medical-generation.ipynb`](08%20生成模块与提示词工程第二部分/notebooks/medical-generation.ipynb) | [`requirements.txt`](08%20生成模块与提示词工程第二部分/requirements.txt) |
| **09** 生成答案评估，缓存策略与批量处理 | [`09 生成答案评估，缓存策略与批量处理/`](09%20生成答案评估，缓存策略与批量处理/) | ✅ **已完成**（0–6） | [`任务.txt`](09%20生成答案评估，缓存策略与批量处理/任务.txt) | [`schedule.md`](09%20生成答案评估，缓存策略与批量处理/schedule.md) | [`answer-eval-cache-batch.ipynb`](09%20生成答案评估，缓存策略与批量处理/notebooks/answer-eval-cache-batch.ipynb) | [`requirements.txt`](09%20生成答案评估，缓存策略与批量处理/requirements.txt) |

**说明**

- 各阶段**具体要求与交付标准**以对应目录内 **`任务.txt`** 为准。
- 各阶段**整体运行入口**在对应 **Jupyter Notebook** 中；按 notebook 内章节顺序执行 cell。

---

## 各阶段完成总结

> 格式统一：**定位 → 任务 → 关键结果 → 产出索引**。实现细节、参数表、踩坑记录见各阶段 `schedule.md` 与 `docs/` 正式报告。

### 01 验证模型（2026-05-13）

- **定位**：工程起点；验证「本地 Ollama + PMC 样本文献 + 向量库 smoke test」是否可行。
- **主要任务**：拉取/解析 PMC XML 样本、本地 `deepseek-r1:7b` 推理、Chroma 最小检索实验。
- **关键结果**：本地 LLM 与样本文献链路跑通；为 02 全量数据处理提供环境与经验。
- **主要产出**：`med-LLM-RAG.ipynb`、`outputs/model_test_results.json`、验证期 XML 样本。
- **详情**：[`01 验证模型/schedule.md`](01%20验证模型/schedule.md)

### 02 数据处理（2026-05-27）

- **定位**：确定全库分割策略与 slim 语料；为 03 分割与 06 元数据回查提供基础数据。
- **主要任务**：验证期 97 篇 + 全量 4,557,627 篇 EDA；输出 `chunk_strategy_config.json`。
- **关键结果**：验证期与全量 P95 token、单块占比一致；策略 `chunk_size=400, overlap=80` **无需调整**。
- **主要产出**：`E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl`（8.9 GB）；[`docs/RAG数据分析与设计说明.md`](02%20数据处理/docs/RAG数据分析与设计说明.md)。
- **详情**：[`02 数据处理/schedule.md`](02%20数据处理/schedule.md)

### 03 文档解析与分割（2026-05-27）

- **定位**：将 slim 转为可检索 chunk；产出样本库（开发）与全量库（生产）。
- **主要任务**：按 02 策略全量分割；验证样本 1,000 篇 → 1,267 chunks。
- **关键结果**：全量 **6,107,296** chunks；token 超限 0；单块比例与验证期一致。
- **主要产出**：`E:\...\oa_comm_chunks.jsonl`；[`chunks_sample.jsonl`](03%20文档解析与分割/data/processed/chunks_sample.jsonl)；[`docs/文档分割处理报告.md`](03%20文档解析与分割/docs/文档分割处理报告.md)。
- **详情**：[`03 文档解析与分割/schedule.md`](03%20文档解析与分割/schedule.md)

### 04 向量化与索引构建（2026-06-03）

- **定位**：语义检索底座；BGE 嵌入 + Chroma 持久化索引。
- **主要任务**：样本 1,267 条验证 + 全量 610 万条建库（GPU）。
- **关键结果**：`pmc_oa_comm_full` 入库 6,107,296 条；384 维 cosine；C3–C5 检索与元数据过滤通过。
- **主要产出**：`04 .../data/chroma_db_full/`（~71 GB，**.gitignore**）；[`docs/向量化与索引报告.md`](04%20向量化与索引构建/docs/向量化与索引报告.md)；`embedder.py` / `index_builder.py`。
- **详情**：[`04 向量化与索引构建/schedule.md`](04%20向量化与索引构建/schedule.md)

### 05 检索系统开发第一部分（2026-06-10）

- **定位**：查询理解层；把自然语言 query 结构化为向量/BM25 查询与 filters。
- **主要任务**：`MedicalQueryEnhancer`、同义词表、双库 smoke（样本 vs 全量 Chroma）。
- **关键结果**：样本库 query ~12 ms、全量 ~16 ms；05→04 检索路径打通。
- **主要产出**：`query_enhancer.py`、`medical_synonyms.json`；[`docs/查询理解与增强报告.md`](05%20检索系统开发第一部分/docs/查询理解与增强报告.md)。
- **详情**：[`05 检索系统开发第一部分/schedule.md`](05%20检索系统开发第一部分/schedule.md)

### 06 检索系统开发第二部分（2026-06-18）

- **定位**：检索执行层；向量 + BM25 → RRF 融合 → cross-encoder 重排。
- **主要任务**：`RetrievalPipeline` 端到端；样本库 5 query 评测 + C12 可选全量联调。
- **关键结果**：样本库 5/5 链路通；全量 metformin query 命中真实 RCT（`PMC2566605`）。**⚠️ 日常 notebook/CLI 默认样本库（1,267 chunks），非 610 万全量。**
- **主要产出**：`pipeline.py`、`pipeline_eval.json`；[`docs/检索流水线报告.md`](06%20检索系统开发第二部分/docs/检索流水线报告.md)。
- **详情**：[`06 检索系统开发第二部分/schedule.md`](06%20检索系统开发第二部分/schedule.md) §「验证范围说明」

### 07 生成模块与提示词工程第一部分（2026-06-24）

- **定位**：生成准备层；把 06 `reranked` 整理为 LLM 可用的 `context_text` 与四阶段 Prompt。
- **主要任务**：`ContextAssembler`（去重/多样化/控长）+ `PromptStage` 模板；**本阶段不调用 LLM**。
- **关键结果**：pytest **16 passed**；notebook C0–C7 样例 JSON 导出。
- **主要产出**：`context_assembler.py`、`prompts.py`；[`docs/上下文组装与提示工程报告.md`](07%20生成模块与提示词工程第一部分/docs/上下文组装与提示工程报告.md)。
- **详情**：[`07 生成模块与提示词工程第一部分/schedule.md`](07%20生成模块与提示词工程第一部分/schedule.md)

### 08 生成模块与提示词工程第二部分（2026-07-02）

- **定位**：生成执行层；Ollama 多步生成 + 后处理，串联 05→06→07 产出 `answer` + `sources`。
- **主要任务**：`LLMGenerator`、`MedicalGenerationPipeline`、引用后处理；批量评测 `generation_eval.json`。
- **关键结果**：pytest **17 passed**；4 条基准 query 快照（基于 **06 样本库** `pipeline_eval.json` + 本机 Ollama）。
- **主要产出**：`generation_pipeline.py`、`run_generation_eval.py`；[`docs/医学生成流水线报告.md`](08%20生成模块与提示词工程第二部分/docs/医学生成流水线报告.md)。
- **详情**：[`08 生成模块与提示词工程第二部分/schedule.md`](08%20生成模块与提示词工程第二部分/schedule.md)

### 09 生成答案评估，缓存策略与批量处理（2026-07-08）

- **定位**：质量与工程优化横切层；在 08 外侧做评估、缓存、批量调度，不改变 08 生成内核。
- **主要任务**：`AnswerEvaluator`（ROUGE/recall/幻觉风险/可读性）、`GenerationCache`、`BatchRunner`、`PipelineWithEval`。
- **关键结果**：pytest **18 passed**；offline 第二轮缓存命中率 **1.0**；rouge1_avg=0.0768、key_info_recall_avg=0.2321（**样本库链路**，见报告 §1.2）。
- **主要产出**：`pipeline_with_eval.py`、`eval_cache_batch_report.json`；[`docs/答案评估与缓存报告.md`](09%20生成答案评估，缓存策略与批量处理/docs/答案评估与缓存报告.md)。
- **详情**：[`09 .../schedule.md`](09%20生成答案评估，缓存策略与批量处理/schedule.md)（含全量复评占位）

---

## Python 环境与依赖

### 推荐环境

| 项 | 值 |
|----|-----|
| Conda 环境名 | `med-rag-verify`（01–09 共用） |
| Python | 3.11.x |
| 平台 | Windows / macOS |

### 一键安装（推荐）

```powershell
# Windows：创建环境 + 01/02 基础依赖
.\setup_windows_env.ps1

# 安装 01→09 全部 Python 依赖（含 04–09）
.\install_all_requirements.ps1

# 或手动逐阶段（03 无新增，可跳过）：
# pip install -r "01 验证模型/requirements.txt"
# pip install -r "02 数据处理/requirements.txt"
# ... 见 requirements.txt 清单
```

根目录 [`requirements.txt`](requirements.txt) 记录安装顺序；因目录名含空格，请用 [`install_all_requirements.ps1`](install_all_requirements.ps1) 而非 `pip install -r requirements.txt`。

### 分阶段新增依赖一览

| 阶段 | `requirements.txt` | 相对上一阶段新增 / 说明 |
|------|-------------------|-------------------------|
| 01 | [`01 .../requirements.txt`](01%20验证模型/requirements.txt) | Jupyter、pandas、datasets、lxml、chromadb、LangChain、torch（CPU 默认）等全量锁定 |
| 02 | [`02 .../requirements.txt`](02%20数据处理/requirements.txt) | matplotlib、seaborn、sentence-transformers 等 |
| 03 | [`03 .../requirements.txt`](03%20文档解析与分割/requirements.txt) | **无新增**（文档说明；复用 02：langchain-text-splitters 等） |
| 04 | [`04 .../requirements.txt`](04%20向量化与索引构建/requirements.txt) | chromadb、BGE 相关（复用 02 的 sentence-transformers；`embedder.py` 直载 transformers） |
| 05 | [`05 .../requirements.txt`](05%20检索系统开发第一部分/requirements.txt) | 查询增强相关（基本复用 04） |
| 06 | [`06 .../requirements.txt`](06%20检索系统开发第二部分/requirements.txt) | **`rank-bm25`** |
| 07 | [`07 .../requirements.txt`](07%20生成模块与提示词工程第一部分/requirements.txt) | **无强制新增**（可选 gpt2 tokenizer） |
| 08 | [`08 .../requirements.txt`](08%20生成模块与提示词工程第二部分/requirements.txt) | **`httpx`**（Ollama HTTP） |
| 09 | [`09 .../requirements.txt`](09%20生成答案评估，缓存策略与批量处理/requirements.txt) | **`rouge-score`**、`pytest`（httpx 与 08 重叠） |

### 04 全量 GPU 补充（可选）

> 01 默认 PyPI 的 torch 常为 **CPU 版**。01–03 不依赖 GPU；**04 全量 610 万嵌入**前需 CUDA 版 torch。

```powershell
.\setup_stage04_gpu.ps1
# 或：pip uninstall torch -y && pip install torch --index-url https://download.pytorch.org/whl/cu124
```

验证：`torch.cuda.is_available()` 为 `True`。勿在 GPU 配置后用 `pip install -r 01.../requirements.txt` 覆盖回 CPU 版。详见原 04 notebook 踩坑：`笔记/04笔记.md` Q12。

---

## 本地部署指南

> 从 GitHub 克隆后的搭建顺序：**环境 → 大文件/模型 → 按阶段 notebook 或 CLI 运行**。

### 1. 克隆与 Python 环境

```powershell
git clone <repo-url> "D:\谷歌"
cd "D:\谷歌"
.\setup_windows_env.ps1
.\install_all_requirements.ps1
```

### 2. `.gitignore` 与未上传内容

以下**不会**随仓库提供，需在本地准备或运行后生成：

| 类型 | 路径 / 模式 | 说明 | 获取方式 |
|------|-------------|------|----------|
| 缓存 | `**/caches/`、`__pycache__/`、`.ipynb_checkpoints/` | HF/datasets 缓存、运行时生成 | 首次运行自动创建 |
| 密钥 | `.env`、`secrets/` | 勿提交 | 本地自建（若需要） |
| Ollama 模型 | `**/ollama_models/`、`deepseek-r1:7b` | 01/08 LLM | `ollama pull deepseek-r1:7b` |
| 验证期向量库 | `**/chroma_db/` | 04 样本库（可 notebook 重建） | 跑 `vectorize-index.ipynb` |
| **全量向量库** | `**/chroma_db_full/`（~71 GB） | 04 生产检索 | D: 本地保留或 E: 备份；整目录复制 |
| **slim JSONL** | `**/oa_comm_slim.jsonl`（~8.9 GB） | 02/03/06 元数据回查 | 02 全量生成；复制到 `06 .../data/` |
| **全量 chunks** | `E:\...\oa_comm_chunks.jsonl`（~9.1 GB） | 03/04 全量 BM25/重建索引 | 03 全量分割产出 |
| PMC 原始压缩包 | 外接盘 ~100 GB+ | 02 全量解析 | 按 02 notebook partB 说明 |

**已随仓库提供（可直接用）**：01 验证 XML、02/03 样本 JSONL、04 样本 chunks 与统计 JSON、05–09 代码与样例输出 JSON 等（见下表）。

| 数据 | 位置 | 说明 |
|------|------|------|
| 01 验证期 XML | `01 验证模型/data/raw/extracted/` | 284 篇 |
| 02 验证样本 | `02 数据处理/data/processed/sample*.jsonl` | 100→97 篇清洗后 |
| 03 验证 chunks | `03 .../data/processed/chunks_sample.jsonl` | **1,267**（开发默认语料） |
| 04 验证 chunks | `04 .../data/processed/chunks_sample.jsonl` | 复制自 03 |
| 04 全量统计 JSON | `04 .../outputs/tables/index_stats.json` 等 | 建库验证报告（库本体在本地 D:/E:） |

### 3. Ollama（阶段 01 / 08）

```bash
cd "01 验证模型"
export OLLAMA_MODELS="$(pwd)/ollama_models"   # Windows 见 notebook 说明
ollama pull deepseek-r1:7b
```

确保 `http://127.0.0.1:11434` 可访问后再跑 08/09 `--mode live`。

### 4. 按阶段运行

1. **File → Open Folder** → 选择对应阶段目录  
2. Jupyter 内核：**`med-rag-verify`**  
3. 按 notebook 章节顺序执行（04 全量：`vectorize-index-full.ipynb` C0→C5）  
4. CLI 示例见「各阶段交付物速查」

### 5. 生产 RAG 数据切换提醒

开发阶段 06–09 默认 **样本库（1,267 chunks）**；上线 LangChain RAG 须切换 **全量**：

- Chroma：`04 .../chroma_db_full` · `pmc_oa_comm_full`
- BM25：`E:\med-llm-rag-datasets\processed\oa_comm_chunks.jsonl`
- 代码：`RetrievalPipeline.from_mode("full")`

---

## 各阶段交付物速查

> 面向**后续开发**：路径、⚠️ 边界、可调用接口、**schedule 实现注意事项**（精炼）。完整踩坑见各阶段 `schedule.md`。

### 01 验证模型（✅）

- **产出**：`outputs/model_test_results.json`；`data/processed/sample.jsonl`
- **入口**：`med-LLM-RAG.ipynb`
- **接口**：Ollama 本地服务 + Chroma smoke（见 notebook §6）
- **后续开发注意**（[`schedule.md`](01%20验证模型/schedule.md)「关键发现」）：
  - Ollama **`think=False`**，否则 deepseek-r1 思考链占满 token、易超时（08+ 沿用）。
  - 纯 LLM 无文献时医学准确性不足——RAG 价值实证。
- **详情**：[`schedule.md`](01%20验证模型/schedule.md)

### 02 数据处理（✅）

- **产出**：[`docs/RAG数据分析与设计说明.md`](02%20数据处理/docs/RAG数据分析与设计说明.md)；`outputs/tables/chunk_strategy_config.json`
- **全量数据**：`E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl`（**不在 Git**）
- **接口**：`src/parse_pmc.py`、`build_jsonl.py`、`full_scale_pipeline.py`
- **后续开发注意**（[`schedule.md`](02%20数据处理/schedule.md)）：
  - 本阶段不做向量入库与 LLM；slim 为 03 分割与 06 元数据回查上游。
  - 策略 `chunk_size=400, overlap=80` 已全量验证，报告 §8 含数据侧 RAG 建议。
- **详情**：[`schedule.md`](02%20数据处理/schedule.md)

### 03 文档解析与分割（✅）

- **产出**：[`docs/文档分割处理报告.md`](03%20文档解析与分割/docs/文档分割处理报告.md)；[`chunks_sample.jsonl`](03%20文档解析与分割/data/processed/chunks_sample.jsonl)（1,267）
- **全量**：`E:\...\oa_comm_chunks.jsonl`（6,107,296，**不在 Git**）
- **接口**：`src/chunker.py`
- **后续开发注意**（[`03/04 schedule.md`](03%20文档解析与分割/schedule.md)）：
  - 样本为前 1,000 篇完整文献，供 04–09 开发；**生产 BM25 须全量 chunks**。
  - chunk metadata **无 pub_year**（年份在 06 检索后回查 slim）。
- **详情**：[`schedule.md`](03%20文档解析与分割/schedule.md)

### 04 向量化与索引构建（✅）

- **产出**：[`docs/向量化与索引报告.md`](04%20向量化与索引构建/docs/向量化与索引报告.md)；`src/embedder.py`、`index_builder.py`
- **全量库**：`04 .../data/chroma_db_full/` · `pmc_oa_comm_full`（**不在 Git**，~71 GB）
- **接口**：`encode_queries()` / `encode_documents()`；`ChromaIndexBuilder.query()`
- **后续开发注意**（[`schedule.md`](04%20向量化与索引构建/schedule.md) §「**实现注意事项**」）：
  - **建库不加指令、查询必须加** BGE 前缀；漏加静默降准确率，查询用 `encode_queries()`。
  - 建库与查询同一模型 `bge-small-en-v1.5`（384 维），见 `index_stats.json`。
  - **勿用** `chroma_db/`、`chroma_repair_test/`（半成品）；RAG 用 **`chroma_db_full`**。
  - 全量前需 CUDA torch；Jupyter 避免 `sentence_transformers` 崩内核（已改 transformers 直载）。
- **详情**：[`schedule.md`](04%20向量化与索引构建/schedule.md) §「实现注意事项」「阶段收尾」

### 05 检索系统开发第一部分（✅）

- **产出**：`MedicalQueryEnhancer` → `EnhancedQuery`；[`docs/查询理解与增强报告.md`](05%20检索系统开发第一部分/docs/查询理解与增强报告.md)
- **样例**：`outputs/samples/enhancement_examples.json`
- **接口**：`query_enhancer.enhance(query)` → `vector_query` / `keyword_query` / `filters`
- **后续开发注意**（[`schedule.md`](05%20检索系统开发第一部分/schedule.md) §「**已知约束**」）：
  - BGE 查询 instruction **须与 04 一致**，勿自改措辞。
  - `filters` 可解析年份，但 Chroma **无 pub_year metadata**（06 后过滤补偿）。
  - 静态同义词 JSON；开发联调用样本库 1,267 条。
- **详情**：[`schedule.md`](05%20检索系统开发第一部分/schedule.md)

### 06 检索系统开发第二部分（✅）

> **⚠️ 验证范围**：notebook、CLI、`pipeline_eval.json` 均在 **样本库（1,267 chunks）** 完成，**不是** 610 万全量。生产须 `from_mode("full")`。

| 用途 | 开发（sample） | 生产（full） |
|------|----------------|--------------|
| 向量 | `04 .../chroma_db` · `pmc_oa_comm_sample` | `chroma_db_full` · `pmc_oa_comm_full` |
| BM25 | `03 .../chunks_sample.jsonl` | `E:\...\oa_comm_chunks.jsonl` |
| 代码 | `RetrievalPipeline.from_mode("sample")` | **`from_mode("full")`** |

- **产出**：[`docs/检索流水线报告.md`](06%20检索系统开发第二部分/docs/检索流水线报告.md)；`outputs/samples/pipeline_eval.json`
- **接口**：`RetrievalPipeline.run(query)` → `reranked`；`config.resolve_chroma()` / `resolve_chunks_path()` / `resolve_slim_path()`
- **后续开发注意**（[`schedule.md`](06%20检索系统开发第二部分/schedule.md) §「**验证范围说明**」）：
  - 样本库长尾 query 常缺失；**链路正确 ≠ 生产召回质量**，须全量复评。
  - 融合默认 **`rrf`**；recency/authority 靠 slim 回查，不重建 04 索引。
  - `data/oa_comm_slim.jsonl`（~8.9 GB）**不在 Git**；08/09 默认仍消费样本 `pipeline_eval.json`。
- **详情**：[`schedule.md`](06%20检索系统开发第二部分/schedule.md)

```python
from pipeline import RetrievalPipeline
result = RetrievalPipeline.from_mode("sample").run("metformin cardiovascular effects")
top_chunks = result["reranked"]
```

### 07 生成模块与提示词工程第一部分（✅）

- **范围**：组装 + Prompt；**不调用 LLM**
- **契约**：[`输入候选格式约定.md`](07%20生成模块与提示词工程第一部分/输入候选格式约定.md)
- **接口**：`ContextAssembler.assemble(reranked, ...)` → `context_text`；`PROMPT_STAGES` / `render_prompt_stage(...)`
- **后续开发注意**（[`schedule.md`](07%20生成模块与提示词工程第一部分/schedule.md) §「风险与应对」）：
  - 输入首选 06 `reranked`；token 估算与 Ollama 实际 tokenizer 可能偏差。
  - 去重 Jaccard 0.85、同源降权可调；截断在句号边界。
- **详情**：[`schedule.md`](07%20生成模块与提示词工程第一部分/schedule.md)

### 08 生成模块与提示词工程第二部分（✅）

> **⚠️ 验证范围**：`generation_eval.json`（`offline_sample_pipeline_eval`）基于 **06 样本库** + Ollama。

- **产出**：[`docs/医学生成流水线报告.md`](08%20生成模块与提示词工程第二部分/docs/医学生成流水线报告.md)；`outputs/samples/generation_eval.json`
- **接口**：`MedicalGenerationPipeline.run(query)` → `answer` / `sources` / `generation_metrics`
- **CLI**：`scripts/run_generation_eval.py`（读 06 `pipeline_eval.json`）
- **后续开发注意**（[`schedule.md`](08%20生成模块与提示词工程第二部分/schedule.md)）：
  - **`think=False`**、`max_tokens`≥512；JSON 用 `extract_json`/`repair_json`。
  - 证据评估解析失败**不删 chunk**；调试可 `skip_critical_review=True`。
  - 全量切换：06 `from_mode("full")` 后重跑 `run_generation_eval.py` → 供 09 新快照。
- **详情**：[`schedule.md`](08%20生成模块与提示词工程第二部分/schedule.md)

### 09 生成答案评估，缓存策略与批量处理（✅）

> **⚠️ 验证范围**：offline 指标反映**样本库链路**；不能外推全量 RAG 质量。

- **产出**：[`docs/答案评估与缓存报告.md`](09%20生成答案评估，缓存策略与批量处理/docs/答案评估与缓存报告.md)；`eval_cache_batch_report.json`；`ground_truth.json`
- **接口**：`PipelineWithEval.run_with_cache_and_eval(...)` → `generation` / `evaluation` / `cache`
- **CLI**：`scripts/run_eval_cache_batch.py --mode offline|mock|live`；**`pytest` 18 项**
- **后续开发注意**（[`schedule.md`](09%20生成答案评估，缓存策略与批量处理/schedule.md) §「全量语料复评」、报告 §1.2）：
  - ROUGE（质量）与缓存命中（性能）无关；幻觉分为风险信号；`ground_truth` 与样本检索证据基础不同。
  - **`--mode live` 仍用样本 `pipeline_eval.json`**；全量复评：06 full → 08 重跑 → 09 live（待实施）。
  - 跨阶段 `config` 同名时 09 用 `importlib` 加载本地 config。
- **详情**：[`schedule.md`](09%20生成答案评估，缓存策略与批量处理/schedule.md)；报告 §5.7

```python
result = pipe.run_with_cache_and_eval(query, ground_truth_entry=gt, temperature=0.2)
```

### 跨阶段：样本库 → 全量生产（LangChain_RAG 前必读）

| 环节 | 开发默认 | 生产应切换 |
|------|----------|------------|
| 向量检索 | `chroma_db` / 1,267 | `chroma_db_full` / 610 万 |
| BM25 | `chunks_sample.jsonl` | `oa_comm_chunks.jsonl` |
| 检索 | `from_mode("sample")` | **`from_mode("full")`** |
| 生成评测 | 08 样本 `pipeline_eval.json` | 全量 reranked 后重跑 `generation_eval` |
| 答案评估 | 09 offline 快照指标 | 全量链路复评（09 占位） |

出处：[`06 schedule`](06%20检索系统开发第二部分/schedule.md) §验证范围、[`04 schedule`](04%20向量化与索引构建/schedule.md) §实现注意事项。

---

## 笔记目录

`笔记/` 下为**个人学习 Q&A**，记录概念与踩坑，**不属于正式交付物**。

| 文件 | 内容 |
|------|------|
| `01笔记.ipynb` | 量化机制、Ollama 存储原理 |
| `01笔记附chroma.ipynb` | Chroma 工作机制 |
| `02笔记.ipynb` | 数据质量问题诊断与修复 |
| `03笔记.md` | 第三阶段任务理解 Q&A |
| `04笔记.md` | 嵌入模型、维数、token、ChromaDB、BGE 查询指令 Q&A |
| `05笔记·.md` | 05 阶段共识、filter 决策、双库 smoke、notebook 实测 Q&A |
| `06笔记.md` | 06 阶段 RAG 位置、多路检索/融合/rerank 概念 Q&A |
| `07 笔记.md` | 07 阶段 RAG 位置、输入契约、冒烟测试 Q&A |
| `08笔记.md` | 08 阶段 RAG 位置、schedule 审阅、与 07 衔接 Q&A |
| `09笔记.md` | 09 阶段任务定位、评估/缓存/批量设计与 Q4 问答 |

---

## 更新记录

| 日期 | 说明 |
|------|------|
| 2026-05-11 ~ 13 | 01 阶段完成：本地 LLM + PMC 数据源验证 |
| 2026-05-15 ~ 27 | 02 阶段完成：全量 slim 4,557,627 篇，分割策略验证通过 |
| 2026-05-27 | 03 阶段完成：6,107,296 chunks |
| 2026-06-01 ~ 03 | 04 阶段完成：全量 Chroma 建库 + GPU 环境 |
| 2026-06-08 ~ 10 | 05 阶段完成：查询理解与增强 |
| 2026-06-15 ~ 18 | 06 阶段完成：检索流水线 + 样本/全量联调 |
| 2026-06-22 ~ 24 | 07 阶段完成：上下文组装 + Prompt 模板 |
| 2026-06-29 ~ 07-02 | 08 阶段完成：Ollama 生成流水线 + `generation_eval.json` |
| **2026-07-07** | **09 阶段启动**：评估器 / 缓存 / 批量计划与骨架 |
| **2026-07-08** | **09 阶段完成**：pytest 18 passed；正式报告；明确样本库验证边界与全量复评占位 |
| **2026-07-08** | **README 结构重组**：各阶段完成总结归并、`install_all_requirements.ps1`、部署指南对齐 |
| **2026-07-08** | **README 交付物速查补充**：各阶段 `schedule` 实现注意事项 + 跨阶段样本/全量对照表 |

*阶段进度细节以各目录 `schedule.md`「进度记录」为准。*
