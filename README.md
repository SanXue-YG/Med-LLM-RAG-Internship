# 医学 RAG 实习工程 — 总说明

基于 PMC 开放获取文献（`oa_comm`）的本地 LLM + RAG 可行性验证与数据评估项目。工程按阶段拆分目录，每阶段有独立任务书、计划、依赖与 Jupyter 入口。

> **给老师 / 审阅者**：各阶段**任务原文**见各目录下 `任务.txt`；**执行计划与进度**见各目录 `schedule.md`；**正式分析结论**见 02 阶段 `docs/RAG数据分析与设计说明.md`。

---

## 目录结构

```text
谷歌/
├── README.md                 # 本文件（项目总说明）
├── .gitignore                # Git 忽略规则
├── setup_windows_env.ps1     # Windows 环境一键配置脚本
├── 01 验证模型/              # 阶段 1：本地 LLM + PMC 数据源验证（已完成）
├── 02 数据处理/              # 阶段 2：数据加载与评估（已完成）
├── 03 文档解析与分割/        # 阶段 3：文本分割（进行中）
├── ** LangChain_RAG/         # RAG 系统开发（待定）
└── 笔记/                     # 个人学习笔记
```

---

## 阶段一览

| 阶段 | 目录 | 状态 | 任务书 | 计划 | 运行入口（Jupyter） | 依赖 |
|------|------|------|--------|------|---------------------|------|
| **01** 验证模型 | `01 验证模型/` | ✅ 已完成 | `任务.txt` | `schedule.md` | `med-LLM-RAG.ipynb` | `requirements.txt` |
| **02** 数据处理 | `02 数据处理/` | ✅ 已完成 | `任务.txt` | `schedule.md` | `notebooks/med-data-EDA-partA.ipynb`（验证期）· `partB.ipynb`（全量） | `requirements.txt` |
| **03** 文档解析与分割 | `03 文档解析与分割/` | ✅ **已完成** | `任务.txt` | `schedule.md` | `notebooks/doc-chunking.ipynb`（验证）· `doc-chunking-full.ipynb`（全量） | *共用 02 环境* |

**说明**

- 各阶段**具体要求与交付标准**以对应目录内 **`任务.txt`** 为准（老师下发原文）。
- 各阶段**整体运行入口**在对应 **Jupyter Notebook** 中；按 notebook 内章节顺序执行 cell。
- 02 阶段每次打开 notebook 需先运行 **【前置】**（见 notebook 顶部说明）。

---

## 第二阶段完成总结（2026-05-27）

### 核心数据

| 指标 | 验证期 (97篇) | 全量期 (4,557,627篇) | 结论 |
|------|--------------|---------------------|------|
| P95 retrieval tokens | 617 | 612 | ✅ 一致 |
| >512 占比 | 14.4% | 13.7% | ✅ 一致 |
| 单块占比 | 85.6% | 86.4% | ✅ 一致 |
| abstract 丢弃率 | 3% | 8.74% | ⚠️ 偏高但合理 |

### 主要产出

| 产出 | 路径 | 说明 |
|------|------|------|
| **slim JSONL** | `E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl` | 4,557,627 篇，8.9 GB |
| **分析报告** | `02 数据处理/docs/RAG数据分析与设计说明.md` | 正式交付文档 |
| **分割策略** | `02 数据处理/outputs/tables/chunk_strategy_config.json` | 供第三阶段使用 |

### 结论

验证期制定的分割策略（chunk_size=400, overlap=80）经全量验证**无需调整**，可直接用于第三阶段。

---

## 第三阶段完成总结（2026-05-27）

### 核心数据

| 指标 | 验证样本 (1000篇) | 全量 (4,557,627篇) | 结论 |
|------|------------------|-------------------|------|
| 输出 chunks | 1,267 | **6,107,296** | - |
| 单块比例 | 88.8% | 85.5% | ✅ 一致 |
| 多块比例 | 11.2% | 14.5% | ✅ 一致 |
| Token 超限 | 0 | 0 | ✅ 通过 |
| Token P95 | 472 | 472 | ✅ 一致 |

### 主要产出

| 产出 | 路径 | 说明 |
|------|------|------|
| **全量 chunks** | `E:\med-llm-rag-datasets\processed\oa_comm_chunks.jsonl` | 6,107,296 chunks |
| **处理报告** | `03 文档解析与分割/docs/文档分割处理报告.md` | 正式交付文档 |
| **验证样本** | `03 文档解析与分割/data/processed/chunks_sample.jsonl` | 1,267 chunks |

### 结论

第二阶段策略在全量分割中完全验证通过，6,107,296 个 chunk 已准备好供后续向量化使用。

---

## Python 环境与依赖

### 推荐环境

- **Conda 环境名**：`med-rag-verify`（01、02、03 共用）
- **Python**：3.11.x
- **支持平台**：Windows / macOS

### Windows 安装（推荐）

```powershell
# 运行一键配置脚本
.\setup_windows_env.ps1
```

### 手动安装

```bash
# 1. 创建并激活环境
conda create -n med-rag-verify python=3.11 -y
conda activate med-rag-verify

# 2. 安装阶段 01 完整依赖
pip install -r "01 验证模型/requirements.txt"

# 3. 安装阶段 02 增补依赖
pip install -r "02 数据处理/requirements.txt"
```

### 各阶段 `requirements.txt` 说明

| 文件 | 内容 |
|------|------|
| `01 验证模型/requirements.txt` | 全量锁定：Jupyter、pandas、datasets、lxml、chromadb、LangChain 等 |
| `02 数据处理/requirements.txt` | 在 01 基础上增补：matplotlib、seaborn、sentence-transformers 等 |

---

## 本地部署指南

### 1. 无需额外操作（运行时自动生成）

| 路径 / 类型 | 说明 |
|-------------|------|
| `**/caches/` | HuggingFace / datasets 缓存 |
| `**/.ipynb_checkpoints/` | Jupyter 自动检查点 |
| `__pycache__/` | Python 字节码缓存 |
| `.DS_Store` / `._*` | macOS 目录元数据（已在 .gitignore 中忽略） |

### 2. 体积过大、未纳入 Git

| 资源 | 用途 | 阶段 | 获取方式 |
|------|------|------|----------|
| Ollama 模型 `deepseek-r1:7b` | 本地 LLM 推理 | 01 | `ollama pull deepseek-r1:7b` |
| `ollama_models/` | 模型存储 | 01 | 由 Ollama 自动创建 |
| `chroma_db/` | 向量库持久化 | 01 | 运行 notebook §6 生成 |
| **PMC 全量数据** (~100GB 压缩包，解压后 ~466GB) | 全量数据处理 | 02 | 外接硬盘 + `med-data-EDA-partB.ipynb` |
| **slim JSONL** (8.9 GB) | 第三阶段输入 | 02/03 | 第二阶段生成 |
| **chunks JSONL** (~12 GB) | 向量化输入 | 03 | 第三阶段生成 |

### 3. 已随仓库提供的数据

| 数据 | 位置 | 说明 |
|------|------|------|
| 验证期样本 (100篇) | `02 数据处理/data/processed/sample.jsonl` | 标准分析输入 |
| 清洗后 (97篇) | `02 数据处理/data/processed/sample_clean.jsonl` | 丢弃无 abstract |
| 01 验证期 XML | `01 验证模型/data/raw/extracted/` | 284 篇 PMC XML |

### Ollama 模型（阶段 01）

```bash
# 安装 Ollama 后
cd "01 验证模型"
export OLLAMA_MODELS="$(pwd)/ollama_models"
ollama pull deepseek-r1:7b
./start_ollama.sh
```

### 02/03 阶段运行方式

1. **File → Open Folder** → 选择对应阶段目录
2. Jupyter 内核选择 **`med-rag-verify`**
3. 按 notebook 章节顺序执行

---

## Git 未上传内容（`.gitignore` 摘要）

```text
# 缓存与临时
__pycache__/、.ipynb_checkpoints/、.DS_Store、._*

# 密钥
.env、secrets/

# 体积大、可本地重建
**/caches/              # HF / datasets 缓存
**/chroma_db/           # 向量库持久化
**/ollama_models/       # Ollama 模型权重
**/*.bin
```

---

## 各阶段交付物速查

### 01 验证模型（✅ 已完成）

- 本地 LLM 推理验证：`outputs/model_test_results.json`
- PMC 100 篇样本：`data/processed/sample.jsonl`
- Chroma smoke test：见 `med-LLM-RAG.ipynb` §6

### 02 数据处理（✅ 已完成）

- **正式文档**：`docs/RAG数据分析与设计说明.md`
- **全量数据**：`E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl`（4,557,627 篇）
- **分割策略**：`outputs/tables/chunk_strategy_config.json`
- 数据 pipeline：`src/parse_pmc.py`、`src/build_jsonl.py`、`src/full_scale_pipeline.py`
- 分析 notebook：`med-data-EDA-partA.ipynb`（验证期）· `med-data-EDA-partB.ipynb`（全量）
- 统计表与图：`outputs/tables/*.csv`、`outputs/figures/`

### 03 文档解析与分割（✅ 已完成）

- **正式文档**：`docs/文档分割处理报告.md`
- **全量数据**：`E:\med-llm-rag-datasets\processed\oa_comm_chunks.jsonl`（6,107,296 chunks）
- **验证样本**：`data/processed/chunks_sample.jsonl`（1,267 chunks）
- 分割模块：`src/chunker.py`
- 分析 notebook：`doc-chunking.ipynb`（验证）· `doc-chunking-full.ipynb`（全量）
- 统计报告：`outputs/tables/chunking_stats.json`、`outputs/samples/`

---

## 笔记目录

`笔记/` 下为**个人学习 Q&A**，记录概念与踩坑，**不属于正式交付物**。

| 文件 | 内容 |
|------|------|
| `01笔记.ipynb` | 量化机制、Ollama 存储原理 |
| `01笔记附chroma.ipynb` | Chroma 工作机制 |
| `02笔记.ipynb` | 数据质量问题诊断与修复 |
| `03笔记.md` | 第三阶段任务理解 Q&A |

---

## 更新记录

| 日期 | 说明 |
|------|------|
| 2026-05-11 ~ 13 | 01 阶段完成：本地 LLM + PMC 数据源验证 |
| 2026-05-15 | 02 阶段启动：目录骨架、数据 pipeline |
| 2026-05-19 | 02 阶段验证期完成：§1~§6 定稿 |
| 2026-05-24 | 02 阶段全量期启动：Mac→Windows 迁移、外接盘配置 |
| 2026-05-27 | 02 阶段全部完成：4,557,627 篇处理完成，策略验证通过 |
| **2026-05-27** | **03 阶段全部完成**：6,107,296 chunks 生成完成，质量验证通过 |

*阶段进度细节以各目录 `schedule.md` 内「进度记录」为准。*
