# 医学 RAG 实习工程 — 总说明

基于 PMC 开放获取文献（`oa_comm`）的本地 LLM + RAG 可行性验证与数据评估项目。工程按阶段拆分目录，每阶段有独立任务书、计划、依赖与 Jupyter 入口。

> **给老师 / 审阅者**：各阶段**任务原文**见各目录下 `任务.txt`；**执行计划与进度**见各目录 `schedule.md`；**正式分析结论**见各阶段 `docs/`（02：`RAG数据分析与设计说明.md`；03：`文档分割处理报告.md`；04：`向量化与索引报告.md`；05：`查询理解与增强报告.md`）。

---

## 目录结构

```text
谷歌/
├── README.md                 # 本文件（项目总说明）
├── .gitignore                # Git 忽略规则
├── setup_windows_env.ps1     # Windows 环境一键配置脚本
├── setup_stage04_gpu.ps1     # 04 全量向量化：CUDA 版 PyTorch 补充安装
├── 01 验证模型/              # 阶段 1：本地 LLM + PMC 数据源验证（已完成）
├── 02 数据处理/              # 阶段 2：数据加载与评估（已完成）
├── 03 文档解析与分割/        # 阶段 3：文本分割（已完成）
├── 04 向量化与索引构建/      # 阶段 4：嵌入 + ChromaDB 索引（✅ 全量完成）
├── 05 检索系统开发第一部分/  # 阶段 5：查询理解与增强（✅ 已完成）
├── 06 检索系统开发第二部分/  # 阶段 6：多路检索 + 融合 + 重排序（🔄 进行中）
├── ** LangChain_RAG/         # RAG 系统开发（待定）
└── 笔记/                     # 个人学习笔记
```

---

## 阶段一览

| 阶段 | 目录 | 状态 | 任务书 | 计划 | 运行入口（Jupyter） | 依赖 |
|------|------|------|--------|------|---------------------|------|
| **01** 验证模型 | [`01 验证模型/`](01%20验证模型/) | ✅ 已完成 | [`任务.txt`](01%20验证模型/任务.txt) | [`schedule.md`](01%20验证模型/schedule.md) | [`med-LLM-RAG.ipynb`](01%20验证模型/med-LLM-RAG.ipynb) | [`requirements.txt`](01%20验证模型/requirements.txt) |
| **02** 数据处理 | [`02 数据处理/`](02%20数据处理/) | ✅ 已完成 | [`任务.txt`](02%20数据处理/任务.txt) | [`schedule.md`](02%20数据处理/schedule.md) | [`partA.ipynb`](02%20数据处理/notebooks/med-data-EDA-partA.ipynb)（验证）· [`partB.ipynb`](02%20数据处理/notebooks/med-data-EDA-partB.ipynb)（全量） | [`requirements.txt`](02%20数据处理/requirements.txt) |
| **03** 文档解析与分割 | [`03 文档解析与分割/`](03%20文档解析与分割/) | ✅ 已完成 | [`任务.txt`](03%20文档解析与分割/任务.txt) | [`schedule.md`](03%20文档解析与分割/schedule.md) | [`doc-chunking.ipynb`](03%20文档解析与分割/notebooks/doc-chunking.ipynb)（验证）· [`full.ipynb`](03%20文档解析与分割/notebooks/doc-chunking-full.ipynb)（全量） | *共用 02 环境* |
| **04** 向量化与索引构建 | [`04 向量化与索引构建/`](04%20向量化与索引构建/) | ✅ **已完成** | [`任务.txt`](04%20向量化与索引构建/任务.txt) | [`schedule.md`](04%20向量化与索引构建/schedule.md) | [`vectorize-index.ipynb`](04%20向量化与索引构建/notebooks/vectorize-index.ipynb)（验证）· [`full.ipynb`](04%20向量化与索引构建/notebooks/vectorize-index-full.ipynb)（全量） | [`requirements.txt`](04%20向量化与索引构建/requirements.txt) |
| **05** 检索系统开发第一部分 | [`05 检索系统开发第一部分/`](05%20检索系统开发第一部分/) | ✅ **已完成** | [`任务.txt`](05%20检索系统开发第一部分/任务.txt) | [`schedule.md`](05%20检索系统开发第一部分/schedule.md) | [`query-enhancement.ipynb`](05%20检索系统开发第一部分/notebooks/query-enhancement.ipynb) | [`requirements.txt`](05%20检索系统开发第一部分/requirements.txt) |
| **06** 检索系统开发第二部分 | [`06 检索系统开发第二部分/`](06%20检索系统开发第二部分/) | 🔄 **进行中** | [`任务.txt`](06%20检索系统开发第二部分/任务.txt) | [`schedule.md`](06%20检索系统开发第二部分/schedule.md) | [`retrieval-pipeline.ipynb`](06%20检索系统开发第二部分/notebooks/retrieval-pipeline.ipynb) | [`requirements.txt`](06%20检索系统开发第二部分/requirements.txt) |

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

## 第四阶段完成总结（2026-06-02）

> 目标：将文本块向量化，构建 ChromaDB 持久化索引，支持语义检索与元数据过滤。**全量 6,107,296 chunks 已建库并通过 C3–C5 验证。**

### 已确认决策

| 决策项 | 结论 |
|--------|------|
| 嵌入模型 | `BAAI/bge-small-en-v1.5`（384 维） |
| 相似度 | ChromaDB 余弦（`hnsw:space=cosine`） |
| 验证期向量库 | 工程内 `04 .../data/chroma_db/`（需重跑 notebook 重建样本 collection） |
| **全量向量库（RAG 用）** | **`D:\谷歌\04 向量化与索引构建\data\chroma_db_full\`** |
| E: 权威备份 | 手动完成（建议 `E:\med-llm-rag-datasets\chroma_db_full\`） |

### 全量结果（6,107,296 chunks）✅

| 指标 | 结果 | 状态 |
|------|------|------|
| 入库数量 | 6,107,296 = 输入一致 | ✅ |
| 嵌入维度 | 384 | ✅ |
| collection | `pmc_oa_comm_full` | ✅ |
| 语义检索 | C4 通过 | ✅ |
| 元数据过滤 | `strategy=sliding_window`（post-filter 降级） | ✅ |
| 索引统计 | `outputs/tables/index_stats.json` | ✅ |
| 验证报告 | `outputs/tables/query_validation.json` | ✅ |

### 抽样验证（1,267 chunks）✅

| 指标 | 结果 | 状态 |
|------|------|------|
| 入库数量 | 1,267 = 输入一致 | ✅ |
| 自相似性检索 | Top-1 命中自身 | ✅ |
| 语义检索 | 疟疾/象保护/果蝇节律均命中相关文献 | ✅ |

### 主要产出

| 产出 | 路径 | Git |
|------|------|-----|
| **全量向量库** | `04 .../data/chroma_db_full/` | ❌ `.gitignore`（~71 GB，本地/E: 保留） |
| 全量索引统计 | `04 .../outputs/tables/index_stats.json` | ✅ |
| 全量查询验证 | `04 .../outputs/tables/query_validation.json` | ✅ |
| 验证样本输入 | `04 .../data/processed/chunks_sample.jsonl` | ✅ |
| 验证期统计/报告 | `04 .../outputs/samples/index_stats_sample.json` 等 | ✅ |
| **正式报告** | `04 .../docs/向量化与索引报告.md` | ✅ |
| 核心代码 | `src/embedder.py`、`src/index_builder.py` | ✅ |
| 全量 notebook | `notebooks/vectorize-index-full.ipynb` | ✅ |

### RAG 调用向量库

> **日常 RAG 开发**：挂载本机 D: 上暂留的全量库即可；**无需**读取 E: 上 XML 或 `oa_comm_chunks.jsonl`（chunk 文本已写入 Chroma `documents` 字段，内容为 title + abstract）。E: JSONL 仅作**重建索引**保险。

| 项 | 值 |
|----|-----|
| **路径（RAG 活跃）** | `D:\谷歌\04 向量化与索引构建\data\chroma_db_full\` |
| **E: 备份（可选恢复源）** | `E:\med-llm-rag-datasets\chroma_db_full\`（手动备份已完成） |
| **collection 名称** | `pmc_oa_comm_full` |
| **条数** | 6,107,296 |
| **嵌入模型** | `BAAI/bge-small-en-v1.5`（384 维，cosine） |
| **索引统计** | `04 向量化与索引构建/outputs/tables/index_stats.json` |
| **Git** | 向量库目录在 `.gitignore` 中（`**/chroma_db_full/`），**不会**随仓库上传 |

**Python 挂载示例**（与 04 阶段 `index_builder` 一致）：

```python
import sys
from pathlib import Path

STAGE04 = Path(r"D:\谷歌\04 向量化与索引构建")
sys.path.insert(0, str(STAGE04 / "src"))

from embedder import DocumentEmbedder
from index_builder import ChromaIndexBuilder

PERSIST_DIR = STAGE04 / "data" / "chroma_db_full"
COLLECTION = "pmc_oa_comm_full"

embedder = DocumentEmbedder(model_name="BAAI/bge-small-en-v1.5")
builder = ChromaIndexBuilder(
    persist_dir=str(PERSIST_DIR),
    collection_name=COLLECTION,
    embedder=embedder,
)

# 语义检索（查询端自动加 BGE 指令前缀）
results = builder.query("malaria vaccine efficacy", n_results=5)

# 元数据过滤（全库规模下可能走 post-filter 降级，见 schedule §11）
results = builder.query(
    "gene expression",
    n_results=5,
    where_filter={"strategy": "sliding_window"},
)
```

**metadata 字段**：`doc_id`, `chunk_index`, `total_chunks`, `source_title`, `token_count`, `strategy`

**注意**：

1. 查询嵌入须用 `encode_queries()`（或 `ChromaIndexBuilder.query()`），勿对查询文本用 `encode_documents()`。
2. 若 D: 库已删，将 `PERSIST_DIR` 改为 E: 备份路径，或整目录复制回 D: 原路径。
3. 可清理 D: 冗余目录 `data/chroma_db/`、`data/chroma_repair_test/`（~15.7 万条过时半成品，非 RAG 所需）。

---

## 第五阶段完成总结（2026-06-08）

> 目标：对用户自然语言查询做**查询理解与增强**，产出可供后续检索使用的结构化对象；**不包含**混合检索、LLM 生成答案。

### 已确认决策

| 决策项 | 结论 |
|--------|------|
| 查询语言 | **英文优先**（老师确认）；中文后续视时间添加 |
| 嵌入模型 | 与 04 一致：`BAAI/bge-small-en-v1.5` |
| 时间 filter | **解析但不重建索引**；`year_*` 标 `executable=false` |
| 向量库 | 复用 04 `chroma_db`（样本）/ `chroma_db_full`（全量） |

### 主要产出

| 产出 | 路径 | Git |
|------|------|-----|
| 查询增强模块 | `05 .../src/query_enhancer.py` 等 | ✅ |
| 静态同义词表 | `05 .../data/medical_synonyms.json` | ✅ |
| 演示 notebook | `05 .../notebooks/query-enhancement.ipynb` | ✅ |
| 增强样例 | `05 .../outputs/samples/enhancement_examples.json` | ✅ |
| 双库 smoke 对比 | `05 .../outputs/samples/chroma_smoke_compare.json` | ✅ |
| **正式报告** | `05 .../docs/查询理解与增强报告.md` | ✅ |

### 双库 smoke test（`metformin cardiovascular effects`，Top-5）

| 库 | 条数 | HNSW bin | 平均 query |
|----|------|----------|------------|
| 样本 `chroma_db` | 1,267 | ✅ 完整 | ~12 ms |
| 全量 `chroma_db_full` | 6,107,296 | ❌ 无 bin | ~16 ms |

05→04 检索路径已打通；详见 [`05 .../schedule.md`](05%20检索系统开发第一部分/schedule.md) 与 [`笔记/05笔记·.md`](笔记/05笔记·.md) Q11。

---

## Python 环境与依赖

### 推荐环境

- **Conda 环境名**：`med-rag-verify`（01、02、03、04 共用）
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

### 04 全量运行环境（GPU，Windows）

> **备忘**：01 阶段 `requirements.txt` 仅锁定 `torch==2.11.0`，未区分 CPU/CUDA。`setup_windows_env.ps1` 从默认 PyPI 安装时，Windows 会得到 **CPU 版**（`+cpu`）。阶段 01–03 不依赖 GPU，问题直到 04 全量嵌入才暴露。

**何时需要**：运行 `vectorize-index-full.ipynb` 对 610 万 chunks 建库前（抽样验证 1,267 条用 CPU 即可）。

**一键安装（推荐）**：

```powershell
cd "D:\谷歌"
.\setup_stage04_gpu.ps1
```

**手动安装**：

```powershell
conda activate med-rag-verify
pip uninstall torch -y
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install -r "04 向量化与索引构建/requirements.txt"
```

**验证**（本机 2026-06-01 实测）：

| 项 | 结果 |
|----|------|
| 显卡 | NVIDIA GeForce RTX 4080 Laptop GPU |
| 驱动 | 610.47（`nvidia-smi` 可用） |
| torch | `2.6.0+cu124`（自 CPU 版 `2.11.0+cpu` 升级） |
| `cuda_available` | `True` |
| BGE 嵌入 smoke test | 384 维，`device=cuda` ✅ |

```python
import torch
print(torch.__version__)          # 应含 cu124 等，而非 +cpu
print(torch.cuda.is_available())  # True
print(torch.cuda.get_device_name(0))
```

> **说明**：CUDA 版 torch 需从 PyTorch 官方 index 安装，版本号可能与 01 requirements 中的 `2.11.0` 不同（如 `2.6.0+cu124`），属正常现象；勿用 `pip install -r 01.../requirements.txt` 覆盖，否则会重新装回 CPU 版。

**若 C1 加载模型时 Jupyter 内核崩溃**（`The Kernel crashed`）：

| 步骤 | 操作 |
|------|------|
| 1 | 确认已使用最新 `04 .../src/embedder.py`（**transformers 直载**，不经 `sentence_transformers`） |
| 2 | **Kernel → Restart**，从 C0 重新运行（避免旧模块缓存） |
| 3 | C1 通过后再跑 C2；`batch_size` 建议 128（12GB 显存） |
| 4 | 若仍崩溃，可额外执行 `pip install --force-reinstall pyarrow` 与 `pip install ipywidgets` |

**原因简述**：Windows Jupyter 下 `import sentence_transformers` 会经 `pyarrow`/`datasets` 等 native 依赖链，易触发内核级崩溃；CLI 同代码可能正常。本工程已在 `embedder.py` 侧规避。详情见 `笔记/04笔记.md` Q12、`04 .../schedule.md`「问题排查记录」。

**若 C2 出现 SyntaxError（`\n` 字面量）**：参数 cell 应为三行独立赋值（`BATCH_SIZE` / `RESUME` / `RESET`），勿写成一行带 `\n` 的字符串。

### 各阶段 `requirements.txt` 说明

| 文件 | 内容 |
|------|------|
| `01 验证模型/requirements.txt` | 全量锁定：Jupyter、pandas、datasets、lxml、chromadb、LangChain 等 |
| `02 数据处理/requirements.txt` | 在 01 基础上增补：matplotlib、seaborn、sentence-transformers 等 |
| `03 文档解析与分割/requirements.txt` | 复用 02 环境（langchain-text-splitters、sentence-transformers） |
| `04 向量化与索引构建/requirements.txt` | 复用 02 环境 + chromadb、BGE 嵌入模型 |

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
| `chroma_db/` | 向量库（验证期 / 过时半成品） | 01/04 | 01 smoke test；04 样本需重跑 notebook 重建 |
| **PMC 全量数据** (~100GB 压缩包，解压后 ~466GB) | 全量数据处理 | 02 | 外接硬盘 + `med-data-EDA-partB.ipynb` |
| **slim JSONL** (8.9 GB) | 分割输入 / 06 重排回查 | 02/03/06 | 第二阶段生成；**06 本地副本**见下表 |
| **06 slim 本地副本** (~8.9 GB) | recency/authority 回查（`doc_id`→`pub_year`/`journal`） | 06 | 自 `E:\...\oa_comm_slim.jsonl` 复制至 `06 .../data/`；`.gitignore` |
| **chunks JSONL** (~9.1 GB) | 向量化输入 / 重建索引 | 03/04 | 第三阶段生成；E: 备份 |
| **ChromaDB 全量向量库** | 语义检索索引（~71 GB） | 04 / RAG | `04 .../data/chroma_db_full/`（D: 暂留；E: 备份；`.gitignore`） |

### 3. 已随仓库提供的数据

| 数据 | 位置 | 说明 |
|------|------|------|
| 01 验证期 XML | `01 验证模型/data/raw/extracted/` | 284 篇 PMC XML |
| 02 验证期样本 (100篇) | `02 数据处理/data/processed/sample.jsonl` | 02 阶段标准分析输入 |
| 02清洗后 (97篇) | `02 数据处理/data/processed/sample_clean.jsonl` | 丢弃无 abstract |
| **03 验证样本 chunks** | `03 文档解析与分割/data/processed/chunks_sample.jsonl` | 1000 篇分割后的 1267 chunks |
| 03 验证样本统计 | `03 文档解析与分割/outputs/samples/chunking_stats_sample.json` | 验证样本处理统计 |
| 03 验证样本质量报告 | `03 文档解析与分割/outputs/samples/quality_report_sample.json` | 验证样本质量检查结果 |
| 03 全量统计 | `03 文档解析与分割/outputs/tables/chunking_stats.json` | 全量处理统计（6,107,296 chunks） |
| 03 全量质量报告 | `03 文档解析与分割/outputs/tables/quality_report.json` | 全量抽样质量检查结果 |
| **04 验证样本 chunks** | `04 向量化与索引构建/data/processed/chunks_sample.jsonl` | 复制自阶段 3（1,267 chunks） |
| **04 全量索引统计** | `04 向量化与索引构建/outputs/tables/index_stats.json` | 6,107,296 chunks 建库统计 |
| **04 全量查询验证** | `04 向量化与索引构建/outputs/tables/query_validation.json` | C3–C5 验证报告 |
| 04 验证索引统计 | `04 向量化与索引构建/outputs/samples/index_stats_sample.json` | BGE + ChromaDB 建库统计 |
| 04 验证查询报告 | `04 向量化与索引构建/outputs/samples/query_validation_sample.json` | 检索与元数据过滤验证 |

### Ollama 模型（阶段 01）

```bash
# 安装 Ollama 后
cd "01 验证模型"
export OLLAMA_MODELS="$(pwd)/ollama_models"
ollama pull deepseek-r1:7b
./start_ollama.sh
```

### 02/03/04 阶段运行方式

1. **File → Open Folder** → 选择对应阶段目录
2. Jupyter 内核选择 **`med-rag-verify`**
3. 按 notebook 章节顺序执行（04 全量验证/attach：`vectorize-index-full.ipynb` C0→C2.5a→C3–C5）

---

## Git 未上传内容（`.gitignore` 摘要）

```text
# 缓存与临时
__pycache__/、.ipynb_checkpoints/、.DS_Store、._*

# 密钥
.env、secrets/

# 体积大、可本地重建
**/caches/              # HF / datasets 缓存
**/chroma_db/           # 验证期向量库 / 过时半成品
**/chroma_db_full/      # 全量向量库（~71 GB，本地或 E: 保留）
**/chroma_repair_test/  # HNSW 修复测试残留
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

### 04 向量化与索引构建（✅ 已完成）

- **正式文档**：`docs/向量化与索引报告.md`
- **嵌入模型**：`BAAI/bge-small-en-v1.5`（384 维，余弦相似度）
- **全量向量库（RAG）**：`D:\谷歌\04 向量化与索引构建\data\chroma_db_full\`（collection: `pmc_oa_comm_full`，6,107,296 条）
- **E: 备份**：`E:\med-llm-rag-datasets\chroma_db_full\`（手动完成）
- **全量统计/验证**：`outputs/tables/index_stats.json`、`query_validation.json`
- **验证样本**：`data/processed/chunks_sample.jsonl`（1,267 chunks）
- 核心模块：`src/embedder.py`、`src/index_builder.py`
- 验证 notebook：`vectorize-index.ipynb` · 全量 notebook：`vectorize-index-full.ipynb`
- 验证报告（样本）：`outputs/samples/index_stats_sample.json`、`query_validation_sample.json`
- **RAG 调用说明**：见上文「第四阶段完成总结 → RAG 调用向量库」

### 05 检索系统开发第一部分（✅ 已完成）

- **任务范围**：查询理解与增强（任务书本周产出 = 代码模块）
- **核心模块**：`MedicalQueryEnhancer` → `EnhancedQuery`（vector/keyword query + filters）
- **嵌入模型**：`BAAI/bge-small-en-v1.5`（与 04 一致；BGE 指令由 `DocumentEmbedder.encode_queries()` 添加）
- **演示入口**：`notebooks/query-enhancement.ipynb`（C0–C5）
- **样例输出**：`outputs/samples/enhancement_examples.json`、`chroma_smoke_compare.json`
- **联调脚本**：`scripts/run_dual_smoke.py`
- **正式文档**：`docs/查询理解与增强报告.md`

### 06 检索系统开发第二部分（🔄 进行中，阶段 0–3 已完成）

- **任务范围**：多路检索（向量 + BM25）→ 融合 → 重排序；与 05 查询增强打通为完整检索流水线
- **已完成模块**：`bm25_index.py`、`multipath_retriever.py`、`fusion.py`、`reranker.py`、`rerank_features.py`
- **融合默认策略**：**`rrf`**（C7 实测：simple 在双路零重叠时等同纯向量；weighted 与 rrf Top-5 高度一致，rrf 更稳）
- **待完成**：`pipeline.py`（阶段 4 端到端串联）
- **配置入口**：`src/config.py`（`resolve_slim_path()` / `resolve_chunks_path()` / `resolve_chroma()`）
- **slim 回查（RAG 活跃）**：`06 检索系统开发第二部分/data/oa_comm_slim.jsonl`（4,557,627 篇，~8.9 GB；自 E: 复制，不随 Git 上传）
- **嵌入 / 重排模型**：`BAAI/bge-small-en-v1.5`（与 04/05 一致）、`BAAI/bge-reranker-base`（阶段 3）
- **演示入口**：[`notebooks/retrieval-pipeline.ipynb`](06%20检索系统开发第二部分/notebooks/retrieval-pipeline.ipynb)（**C0–C9**，含重排）
- **样例输出**（`outputs/samples/`）：
  - `fusion_examples.json` — 5 条 query 的 RRF 融合结果 + 三策略对比
  - `rerank_examples.json` — 多准则重排结果（C8 导出）
  - `retrieval_compare.json` — 向量 vs BM25 双路诊断（metformin query）
  - `bm25_examples.json`、`vector_smoke_sample.json`
- **Notebook 验证要点**（样本库 1,267 chunks）：
  - 双路 Top-5 可零重叠 → 多路融合有价值；**simple 无法补 BM25，默认用 rrf**
  - rrf 与 weighted Top-5 集合 ~80% 一致；rrf 不依赖分数归一化
  - C8 重排：`year_hint` 已接入；样本库文献偏旧，时效 query 效果待全量验证
- **计划与进度**：[`06 .../schedule.md`](06%20检索系统开发第二部分/schedule.md)

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

---

## 更新记录

| 日期 | 说明 |
|------|------|
| 2026-05-11 ~ 13 | 01 阶段完成：本地 LLM + PMC 数据源验证 |
| 2026-05-15 | 02 阶段启动：目录骨架、数据 pipeline |
| 2026-05-19 | 02 阶段验证期完成：§1~§6 定稿 |
| 2026-05-24 | 02 阶段全量期启动：Mac→Windows 迁移、外接盘配置 |
| 2026-05-27 | 02 阶段全部完成：4,557,627 篇处理完成，策略验证通过 |
| 2026-05-27 | 03 阶段全部完成：6,107,296 chunks 生成完成，质量验证通过 |
| **2026-06-01** | **04 阶段启动**：制定计划、确定 bge-small + 先抽样验证 |
| **2026-06-01** | **04 抽样验证完成**：1,267 chunks 建库与检索验证通过 |
| **2026-06-02** | **04 GPU 环境就绪**：`torch 2.6.0+cu124`（RTX 4080）；`setup_stage04_gpu.ps1` |
| **2026-06-02** | **04 全量完成**：6,107,296 chunks 建库；C3–C5 验证通过；E: 备份完成 |
| **2026-06-02** | **04 收尾文档**：schedule + README 更新；RAG 挂载 D: `chroma_db_full/` |
| **2026-06-03** | **04: 新增向量化与索引正式报告**（`BAAI/bge-small-en-v1.5`） |
| **2026-06-08** | **05 阶段完成**：查询理解与增强模块 + 双库 Chroma smoke test |
| **2026-06-10** | **05: 新增查询理解与增强正式报告** |
| **2026-06-15** | **06 阶段 2 完成**：多路召回 + 三种融合；notebook C0–C8 样本验证；导出 fusion 样例 |
| **2026-06-17** | **06 阶段 3 完成**：BGE reranker + recency/authority；C7 确认 **RRF 为默认融合策略** |

*阶段进度细节以各目录 `schedule.md` 内「进度记录」为准。*
