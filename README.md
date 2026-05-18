# 医学 RAG 实习工程 — 总说明

基于 PMC 开放获取文献（`oa_comm`）的本地 LLM + RAG 可行性验证与数据评估项目。工程按阶段拆分目录，每阶段有独立任务书、计划、依赖与 Jupyter 入口。

> **给老师 / 审阅者**：各阶段**任务原文**见各目录下 `任务.txt`；**执行计划与进度**见各目录 `schedule.md`；**正式分析结论**见 02 阶段 `docs/RAG数据分析与设计说明.md`（随阶段推进更新）。

---

## 目录结构

```text
实习/谷歌/
├── readme.md                 # 本文件（项目总说明）
├── .gitignore                # Git 忽略规则（见下文「未上传内容」）
├── 01 验证模型/              # 阶段 1：本地 LLM + PMC 数据源验证（已完成）
├── 02 数据处理/              # 阶段 2：数据加载与评估（进行中）
├── ** LangChain_RAG/         # 阶段 3（暂缓）：LangChain RAG 系统
└── 笔记/                     # 个人学习笔记
```

---

## 阶段一览

| 阶段 | 目录 | 状态 | 任务书 | 计划 | 运行入口（Jupyter） | 依赖 |
|------|------|------|--------|------|---------------------|------|
| **01** 验证模型 | `01 验证模型/` | ✅ 已完成 | [`任务.txt`](01%20验证模型/任务.txt) | [`schedule.md`](01%20验证模型/schedule.md) | [`med-LLM-RAG.ipynb`](01%20验证模型/med-LLM-RAG.ipynb) | [`requirements.txt`](01%20验证模型/requirements.txt) |
| **02** 数据处理 | `02 数据处理/` | 🔄 进行中（至阶段 3） | [`任务.txt`](02%20数据处理/任务.txt) | [`schedule.md`](02%20数据处理/schedule.md) | [`notebooks/med-data-EDA.ipynb`](02%20数据处理/notebooks/med-data-EDA.ipynb) | [`requirements.txt`](02%20数据处理/requirements.txt)（在 01 环境上增补） |
| **03** LangChain RAG | `** LangChain_RAG/` | ⏸ 暂缓 | — | [`schedule.md`](**%20LangChain_RAG/schedule.md) | *待定* | *待定* |

**说明**

- 各阶段**具体要求与交付标准**以对应目录内 **`任务.txt`** 为准（老师下发原文）。
- 各阶段**整体运行入口**在对应 **Jupyter Notebook** 中；按 notebook 内章节顺序执行 cell。02 阶段每次打开 notebook 需先运行 **【前置 1/2】【前置 2/2】**（见 notebook 顶部说明）。
- 02 阶段另有命令行数据构建：`scripts/build_jsonl.sh`（XML → jsonl，不经过 notebook 也可跑）。

---

## Python 环境与依赖

### 推荐环境

- **Conda 环境名**：`med-rag-verify`（01、02 共用）
- **Python**：3.11.x

### 安装顺序

```bash
# 1. 创建并激活环境（若尚未创建）
conda create -n med-rag-verify python=3.11 -y
conda activate med-rag-verify

# 2. 安装阶段 01 完整依赖（134 行锁定版本）
pip install -r "01 验证模型/requirements.txt"

# 3. 安装阶段 02 增补依赖
pip install -r "02 数据处理/requirements.txt"
```

### 各阶段 `requirements.txt` 说明

| 文件 | 内容 |
|------|------|
| `01 验证模型/requirements.txt` | **全量锁定**：Jupyter、`pandas`、`datasets`、`lxml`、`chromadb`、LangChain 相关等；跑 01 notebook 以此为准。 |
| `02 数据处理/requirements.txt` | **在 01 基础上的增补**：`matplotlib`、`seaborn`、`sentence-transformers` 等；用于 token 统计与可视化（§4~§5）。02 **不单独维护一份完整 pip freeze**，避免与 01 重复。 |

仅跑 **02 数据处理**（不用 Ollama / Chroma）时，仍建议先装 01 的 `requirements.txt`，因环境已按该方式验证；若需极简环境，至少保证：`pandas`、`datasets`、`lxml`、`tqdm`、`ipykernel`，以及 02 增补文件中的分析包。

---

## 本地部署指南

克隆仓库后，除 `pip install` 外，可能需要自行准备以下内容。

### 1. 无需额外操作（被 Git 忽略、运行时可自动生成）

| 路径 / 类型 | 说明 |
|-------------|------|
| `**/caches/` | HuggingFace / datasets 缓存；首次加载 tokenizer 或 `load_dataset` 时自动下载到工程内或用户缓存目录。 |
| `**/.ipynb_checkpoints/` | Jupyter 自动检查点。 |
| `__pycache__/` | Python 字节码缓存。 |
| `.DS_Store` | macOS 目录元数据。 |

02 notebook 前置 cell 会将 `HF_HOME` 指向 `02 数据处理/caches/huggingface`（若已运行前置）；删除后**重新运行 notebook 即可重建**，不影响逻辑。

### 2. 体积过大、未纳入 Git — 需本地自行准备

| 资源 | 用途 | 阶段 | 本地获取方式 |
|------|------|------|----------------|
| **Ollama 模型** `deepseek-r1:7b`（Q4_K_M，约 4.4 GB） | 01 本地 LLM 推理 | 01 | 见下方「Ollama 模型」 |
| **`01 验证模型/ollama_models/`** | 工程内模型存储目录 | 01 | 由 `ollama pull` 写入；`.gitignore` 已忽略 |
| **`01 验证模型/chroma_db/`** | Chroma 持久化向量库 | 01 | 运行 01 notebook **§6** 可重新生成；`.gitignore` 已忽略 |
| **Sentence-Transformers 权重** `all-MiniLM-L6-v2` | 02 token 长度统计（512 上限参照） | 02 | 首次在 §4/§5 调用 `AutoTokenizer.from_pretrained(...)` 或 `sentence-transformers` 时从 HuggingFace 自动下载；需网络。也可预先：`python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')"` |
| **PMC 全量原始包（~100GB+）** | 02 全量评估 | 02（未来） | 外接硬盘 + `build_jsonl.sh`；见 `02 数据处理/schedule.md` 阶段 B |

### 3. 已随仓库提供或可由脚本生成的数据

| 数据 | 位置 | 说明 |
|------|------|------|
| 100 篇结构化样本 | `02 数据处理/data/processed/sample.jsonl` | 02 标准分析输入（由 `parse_pmc.py` 生成） |
| 清洗后 97 篇 | `02 数据处理/data/processed/sample_clean.jsonl` | 丢弃无 abstract 后 |
| 01 验证期 XML（284 篇） | `01 验证模型/data/raw/extracted/` | 若仓库内已包含，可直接用于 `build_jsonl.sh` 重跑；若未上传则见下 |
| 01 旧版 jsonl 备份 | `02 数据处理/data/processed/sample.jsonl.bak01` | 01 解析器生成的历史样本，仅作对比 |

**若仓库未包含 XML 解压目录**：在 01 目录按 [`med-LLM-RAG.ipynb`](01%20验证模型/med-LLM-RAG.ipynb) **§5** 下载并解压 PMC `oa_comm` 样本包，或在 02 执行：

```bash
cd "02 数据处理"
./scripts/build_jsonl.sh --pmcids-from data/processed/sample.jsonl.bak01
# 自动探测 01/data/raw/extracted 或设置 PMC_XML_ROOT
```

### Ollama 模型（阶段 01）

1. 安装 [Ollama](https://ollama.com/)（Mac 版）。
2. 在 **`01 验证模型/`** 目录：

```bash
export OLLAMA_MODELS="$(pwd)/ollama_models"   # 模型存工程内，与 start_ollama.sh 一致
ollama pull deepseek-r1:7b
./start_ollama.sh    # 启动服务；另开终端跑 notebook
```

3. 模型拉取与验证步骤详见 **`01 验证模型/med-LLM-RAG.ipynb`** 章节 2~4（含 `ollama pull deepseek-r1:7b`、API `think=False` 等说明）。

**阶段 02 不需要启动 Ollama**（纯数据处理与 tokenizer 统计）。

### 02 阶段运行方式（VS Code）

1. **File → Open Folder** → 选择 `02 数据处理/`  
2. Jupyter 内核选择 **`med-rag-verify`**  
3. 打开 `notebooks/med-data-EDA.ipynb`，先运行 **【前置 1/2】【前置 2/2】**，再跑各 § 章节  

---

## Git 未上传内容（`.gitignore` 摘要）

以下内容**故意不提交**到 GitHub，克隆后按上节「本地部署」处理即可。

```text
# 缓存与临时
__pycache__/、.ipynb_checkpoints/、.DS_Store

# 密钥
.env、secrets/

# 体积大、可本地重建
**/caches/              # HF / datasets 缓存
**/chroma_db/           # 向量库持久化
**/ollama_models/       # Ollama 模型权重（~4GB+）
**/*.bin、data_level0.bin
```

**仍会提交的内容（便于审阅）**：notebook、Python 源码、`sample.jsonl`（约 4.5MB）、分析表格 CSV、计划与说明文档等。若后续单文件超过 GitHub 100MB 限制，需改用 Git LFS 或外置存储。

---

## 各阶段交付物速查

### 01 验证模型（已完成）

- 本地 LLM 推理验证：`outputs/model_test_results.json`
- PMC 100 篇样本（01 版解析）：`data/processed/sample.jsonl`
- Chroma smoke test：见 `med-LLM-RAG.ipynb` §6

### 02 数据处理（进行中）

- 数据 pipeline：`src/parse_pmc.py`、`src/build_jsonl.py`、`src/load_pipeline.py`
- 分析 notebook：`notebooks/med-data-EDA.ipynb`（§3 已完成）
- 正式文档（撰写中）：`docs/RAG数据分析与设计说明.md`
- 分析表：`outputs/tables/*.csv`

---

## 笔记目录

`笔记/` 下为**个人学习 Q&A**（如 `01笔记.ipynb`、`02笔记.ipynb`），记录概念与踩坑，**不属于正式上交交付物**，供自行复习。

---

## 更新记录

| 日期 | 说明 |
|------|------|
| 2026-05-15 | 初版 readme；02 阶段完成至 schedule 阶段 3；补充 02 `requirements.txt` |

*阶段进度细节以各目录 `schedule.md` 内「进度记录」为准。*
