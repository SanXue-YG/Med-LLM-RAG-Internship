# 第二阶段任务计划：数据加载与评估

> 任务来源：`任务.txt`（老师下发：数据加载与评估）
> 阶段目标：在 PMC `oa_comm` 样本上完成 **数据 pipeline + 质量/领域/长度分析**，并输出 **《RAG 数据分析与设计说明》**
> 边界：**本阶段不做 RAG 系统**（不接 Chroma 入库、不接 LangChain 检索链、不跑 LLM 生成）
> **当前状态：✅ 第二阶段全部完成**（2026-05-27）

---

## 📊 阶段目标与交付（请先读）

### 任务原文（节选）

> 数据加载与评估 · `from datasets import load_dataset` · data pipeline  
> 1. 数据结构分析 · 2. 领域内容理解 · 3. 文本特征量化（token）· 4. 制定文本分割策略  
> 交付：《RAG 数据分析与设计说明》

### 本阶段要完成什么

| 模块 | 产出 |
|---|---|
| **数据加载 pipeline** | 可复用的加载代码（JSONL → `datasets` / `pandas`），支持统计与抽样 |
| **§1 数据结构** | 字段缺失率、清洗策略、基础质量、元数据可用性（journal / 年份 / 追溯 ID） |
| **§2 领域内容** | 短/中/长摘要分层样例、术语与结构观察（IMRaD、缩写、同义表述） |
| **§3 文本长度** | 按 **目标 embedding 模型 tokenizer** 的 token 分布（P50/P95/P99） |
| **§4 分割策略** | 基于分布给出 chunk 方案（不分割 / 滑动窗口 / 按章节），附理由 |
| **正式交付** | `docs/RAG数据分析与设计说明.md`（或同名 md）+ 分析 notebook 留档 |

### 本阶段明确不做

- ❌ 向量库入库、embedding 批量生产（仅 **用 tokenizer 做长度统计**）
- ❌ LangChain RAG 链、Ollama 问答、检索评测
- ❌ 全量 PMC baseline（上百 GB）下载工程
- ❌ 阿里云/OSS（除非老师要求扩大样本量且本地盘不够）

---

## 与 `01 验证模型` 的衔接

### 01 仅作参考，数据处理在 02 完成

| 资产 | 路径 | 02 中的用法 |
|---|---|---|
| 原始 XML（验证期） | `01 验证模型/data/raw/extracted/`（284 篇） | **可选**输入；由 `build_jsonl` 自动探测，或设 `PMC_XML_ROOT` |
| 结构化样本 | `02 数据处理/data/processed/sample.jsonl` | **`src/parse_pmc.py` + `scripts/build_jsonl.sh` 生成**，不依赖 01 jsonl |
| 01 旧 jsonl | `01 .../sample.jsonl` | 仅作历史对比；已备份为 `sample.jsonl.bak01` |
| Conda 环境 | `med-rag-verify` | 已含 `pandas`, `datasets`, `lxml`, `tqdm` 等 |
| Jupyter | **VS Code** + 内核 `med-rag-verify` | 不跑 Ollama / 不用 Cursor Jupyter |

### 02 标准数据流（XML → JSONL → 分析）

```text
oa_comm 下载/解压          build_jsonl.sh / build_jsonl.py          partA（验证）/ partB（全量）
─────────────────  →  ─────────────────────────────────────  →  ─────────────────
raw/*.tar.gz            PMC_XML_ROOT 或 data/raw/extracted/          load_pipeline
extracted/**/*.xml      → data/processed/*.jsonl                     §3~§6 分析
（全量期在外接盘）       （全量期 MED_RAG_DATA_ROOT/processed/）
```

**验证期已执行**（2026-05-15）：用修正版 parser 按原 100 个 `pmcid` 重生成 `sample.jsonl`（title/pub_year/pmid/pub_date 已修复）。

### 数据质量问题（01 旧 jsonl · 已用 02 parser 修复）

> 成因与影响见 `笔记/02笔记.ipynb`；**当前 `sample.jsonl` 已由 02 重生成**。

| 问题 | 01 旧数据 | 02 重跑后（100 篇） |
|---|---|---|
| title 污染 | 96/100 >500 字符 | **0/100** >500 字符 |
| pub_year 异常 | 85/100 重复年 | 单一年份字符串 |
| pmid | 无字段 | 已抽取（约 7 篇仍无 pmid，属源 XML 缺失） |
| pub_date | 无字段 | 已抽取 ISO 日期 |
| abstract 缺失 | 3% | 仍为 3%（源数据或结构问题，§3 定丢弃策略） |

### 数据策略（已确认）

采用 **方案 A**：本工程自建 `data/`，与 `01 验证模型` 目录解耦；**不把分析产物写回 01**。

分两阶段推进：

| 阶段 | 数据范围 | 存储位置 | 目的 |
|---|---|---|---|
| **A. 代码验证期**（当前） | **100 篇**（与旧样本同 pmcid，02 parser 重生成） | `02 数据处理/data/processed/sample.jsonl` | 快速跑通 pipeline、统计与 notebook 全章节逻辑 |
| **B. 全量评估期**（代码验证通过后） | PMC `oa_comm` **全库**（约 **100 GB+** 原始包） | **外接硬盘**（Mac 本机盘不承载全量） | 按任务书做完整数据结构与领域评估；结论写入说明文档 |

**验证期生成 jsonl**（在 `02 数据处理` 下）：

```bash
# 默认自动找 01 的 extracted/（或设 PMC_XML_ROOT）；按旧样本 pmcid 对齐重跑
./scripts/build_jsonl.sh --pmcids-from data/processed/sample.jsonl.bak01

# 或：取前 100 个 XML
./scripts/build_jsonl.sh --limit 100
```

**全量期工程约定**（代码已预留，100 篇验证通过后切换环境变量即可）：

| 项 | 验证期 A | 全量期 B |
|---|---|---|
| 数据根 | `02 数据处理/data/` | `MED_RAG_DATA_ROOT=/Volumes/Lexar/med-llm-rag-datasets`（**已验证 2026-05-19**） |
| XML | `01.../extracted` 或本工程 `data/raw/extracted` | `$MED_RAG_DATA_ROOT/extracted/`（`PMC_XML_ROOT`） |
| 主 jsonl | `sample.jsonl`（**含 body**，便于本地验证） | `oa_comm_slim.jsonl`（**不含 body 正文**） |
| 清洗 | notebook 丢弃 3 篇 → `sample_clean.jsonl`（仅验证期） | **`build_jsonl --skip-no-abstract`** 解析阶段直接不写无 abstract 篇 |
| 索引 | 不需要 | `pmcid_index.jsonl`（建库前扫一遍 XML，避免百万次 glob） |
| notebook 加载 | 默认 `sample.jsonl` | `export MED_RAG_JSONL=$MED_RAG_DATA_ROOT/processed/oa_comm_slim.jsonl` |

**外接盘目录布局**：

```text
/Volumes/Lexar/med-llm-rag-datasets/   # MED_RAG_DATA_ROOT（Lexar 外接盘，已验证可写）
├── raw/                          # oa_comm/*.tar.gz
├── extracted/                    # 解压 XML（权威正文，只保留一份）
└── processed/
    ├── oa_comm_slim.jsonl        # 主分析表：元数据 + title + abstract + n_chars_body
    ├── pmcid_index.jsonl         # pmcid → 相对路径（build_pmcid_index.sh）
    ├── skipped_no_abstract.txt   # 解析阶段丢弃的 pmcid（可选审计）
    └── stats/                    # token 分位数、完整性表等（小文件）
```

**为何 slim + 解析阶段丢弃 abstract？**

- §1 任务书**不要求** jsonl 存 body 全文；验证期保留 body 仅为方便 notebook 本地试验。
- 全量若每行带 body，jsonl 体积≈再抄一遍正文；**slim 只保留 `n_chars_body`** 即可做 §1 正文规模统计。
- 验证期已决策：**无 abstract 丢弃**（3%）；全量期在 `parse` 时 `--skip-no-abstract`，**不再生成第二份 `*_clean.jsonl`**。
- §2 领域理解、§3 摘要 token、§4 摘要分割：**只读 slim jsonl**；§3 body token / §4 正文策略：**按 `pmcid` 回查 XML**（`src/pmc_index.py`）或抽样流式扫 XML。

**阶段 B 工作流**：

1. 外接硬盘挂载，创建 `med-rag-pmc/{raw,extracted,processed}`  
2. `export MED_RAG_DATA_ROOT=...`；批次下载 → 解压到 `extracted/`  
3. `./scripts/build_pmcid_index.sh` → `processed/pmcid_index.jsonl`  
4. `./scripts/build_full_slim.sh` → `oa_comm_slim.jsonl` + `skipped_no_abstract.txt`  
5. `export MED_RAG_JSONL=$MED_RAG_DATA_ROOT/processed/oa_comm_slim.jsonl`；notebook 复跑 §1~§6（说明文档分「100 篇验证」与「全量统计」）  
6. body 相关统计：抽样或 `body_token_stats` 流式读 XML（不必把 body 写回 jsonl）

> 100 篇足以完成分析**方法论**与交付结构；全量用于分位数与缺失率更可信。

---

## 阶段总览

| 阶段 | 主题 | 预计耗时 | 状态 | 关键产出 |
|---|---|---|---|---|
| 0 | 概念与指标约定 | 0.5 天 | ✅ | notebook §0 + `load_pipeline` 常量 |
| 1 | 工程骨架 + 环境 | 0.5 天 | ✅ | 目录、VS Code、`build_jsonl`、notebook 前置单元 |
| 2 | 数据加载 pipeline | 1 天 | ✅ | notebook §2 + `src/load_pipeline.py` |
| 3 | 数据结构分析（任务 §1） | 1 天 | ✅ | notebook §3 + `field_completeness.csv` + `sample_clean.jsonl` |
| 4 | 领域内容理解（任务 §2） | 1 天 | ✅ | `domain_analysis.py` + §4 + `stratified_*.md` + 表 |
| 5 | Token 长度分析（任务 §3） | 0.5 ~ 1 天 | ✅ | `token_stats.py` + §5 + `token_percentiles.csv` + ECDF；`docs/...` §5 定稿 |
| 6 | 分割策略设计（任务 §4） | 0.5 天 | ✅ | `chunk_strategy.py` + §6 + `chunk_strategy_*.csv/json` |
| 7 | 交付整理 | 0.5 天 | 🔄 | 《说明》定稿 + checklist |

> 合计约 **4 ~ 5 个工作日**（按每天有效专注 4~6 小时估算，可按老师节奏压缩/拉长）

---

## 阶段 0：概念与指标约定

### 0.1 需要先理解的概念

| 概念 | 本阶段用途 |
|---|---|
| **Data pipeline** | 从原始/半结构化数据 → 统一表结构 → 可统计、可抽样、可写文档，不是 RAG 在线服务 |
| **`datasets.load_dataset`** | 用 Hugging Face `datasets` 读本地 JSONL（`load_dataset("json", data_files=...)`），便于 `map`/`filter`；PMC 无官方单一 HF 数据集名，**不强行 `load_dataset("某医学集")`** |
| **字段缺失率** | 空字符串 / null / 仅空白 的比例；`abstract` >1% 缺失需写清洗策略（丢弃 vs 填充） |
| **Tokenizer（统计用）** | 用**拟定 embedding 模型**的分词器计 token，预测 chunk 是否超限 |
| **Chunk / Split** | 本阶段只**设计策略**；真正 bulk 切分留 RAG 阶段 |

### 0.2 本阶段暂定技术选型（可写入说明文档，RAG 阶段可再议）

| 项 | 暂定选择 | 理由 |
|---|---|---|
| 分析样本 | **验证期 100 篇** → **全量期外接硬盘全库** | 100 篇跑通代码；全量（~100GB+）做完整评估 |
| 统计用 tokenizer | `sentence-transformers/all-MiniLM-L6-v2`（上限 **512 tokens**） | 与后续 RAG 常见起步 embedding 一致；任务书以 512 为参照 |
| 主分析字段（检索单元） | `title + abstract` 为主；`body` 单独统计 | 摘要做检索块；正文过长需单独策略（01 已见 body 均长 ~39k 字符） |
| 清洗阈值（初稿） | `abstract` 缺失率 >1% → 记录并决策；极短 abstract（如 <50 字符）→ 标记低质量 | 与任务书一致，最终以实测为准 |

### 0.3 字段字典（与任务书对齐）

| 任务书字段 | 当前 jsonl | 本阶段处理 |
|---|---|---|
| `title` | ✅（需修 XPath 后重跑更准） | 完整性 + 长度 |
| `journal` | ✅ | 元数据过滤可行性 |
| `pub_date` | ⚠️ 现为 `pub_year` | 分析年份分布；若要做「近 5 年」需补全日期或约定用 year |
| `pmid` | ❌ 未抽取 | 从 XML 增加 `//article-id[@pub-id-type='pmid']`；用于 `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` 追溯 |
| `abstract` / `body` | ✅ | 缺失率、token 长度、分割策略 |
| `pmcid` | ✅ | 主键；PMC 链接 `https://www.ncbi.nlm.nih.gov/pmc/articles/PMCxxxx/` |

---

## 阶段 1：工程骨架 + 环境

### 1.1 建议目录结构（随进度创建）

```text
02 数据处理/
├── 任务.txt
├── schedule.md                 # 本文件
├── requirements.txt            # 在 01 基础上增补（见下）
├── data/                       # 方案 A；验证期 processed/ 含 sample.jsonl 副本
│   ├── raw/                    # 验证期可空；全量期 raw/ 可放在外接盘
│   └── processed/
│       ├── sample.jsonl        # 验证期 100 篇（含 body）
│       ├── sample_clean.jsonl  # 验证期清洗副本（97 篇，全量期不生成）
│       ├── oa_comm_slim.jsonl  # 全量期主表（slim，在外接盘 processed/）
│       └── pmcid_index.jsonl   # 全量期 pmcid → xml 路径
│   # 全量期：MED_RAG_DATA_ROOT 指向外接盘
├── scripts/
│   ├── build_jsonl.sh          # XML → jsonl（支持 --slim）
│   ├── build_full_slim.sh      # 全量 slim 一键入口
│   └── build_pmcid_index.sh    # 预建 pmcid 索引
├── src/
│   ├── parse_pmc.py            # JATS 解析 + pmcid 路径推算
│   ├── pmc_index.py            # 索引构建 + 按需读 body
│   ├── build_jsonl.py          # 批量构建
│   └── load_pipeline.py        # jsonl → Dataset（full/slim）
├── notebooks/
│   ├── med-data-EDA-partA.ipynb  # 验证期 §3～§6（定稿，只读回顾）
│   └── med-data-EDA-partB.ipynb  # 全量期 B0～B6（外接盘）
├── outputs/
│   ├── figures/                # 长度分布等图
│   └── tables/                 # csv/统计表
└── docs/
    └── RAG数据分析与设计说明.md   # 最终交付
```

### 1.2 环境与 Jupyter（VS Code）

- [ ] 复用 conda 环境 **`med-rag-verify`**（推荐，免重复装包）
- [ ] 增补依赖（按需 `pip install` 后写入 `requirements.txt`）：
  - `matplotlib` / `seaborn`（分布图）
  - `transformers` 或 `sentence-transformers`（仅加载 tokenizer）
  - 可选：`wordcloud` / `collections.Counter`（高频词，任务标注 optional）
- [ ] **VS Code**：用 **File → Open Folder** 打开 `02 数据处理/`；安装扩展 **Python** + **Jupyter**
- [ ] **内核**：在 partA / partB notebook 右上角选择 **`med-rag-verify`**
- [ ] **每次重开 notebook**：先跑 **【前置 1/2】→【前置 2/2】**（含 `importlib.reload`，避免 `load_pipeline` 缓存导致 ImportError）
- [ ] **本阶段不启动** `start_ollama.sh`（无 LLM 推理，仅数据处理与 tokenizer 统计）
- [ ] notebook 第一节定义 `PROJECT_DIR`（指向 `02 数据处理/`）；可选设 `HF_HOME` 到 `caches/huggingface` 避免缓存散落

### 1.3 决策记录

| 项 | 选定 / 待定 | 备注 |
|---|---|---|
| 样本量 | 验证 100 篇 → 全量 oa_comm（~100GB+） | 全量放外接硬盘，代码验证通过后再下载 |
| 数据存放 | **方案 A** + 100 篇 **复制至本工程** | `MED_RAG_DATA_ROOT` 切换本机/外接盘 |
| Embedding 参照模型 | MiniLM-L6-v2, 512 tokens | 仅统计 |
| 正文是否纳入首轮 chunk 设计 | 待定 | 建议摘要定策略，正文单列「二期」 |

---

## 阶段 2：数据加载 pipeline

> 对应任务：`from datasets import load_dataset` + data pipeline

### 2.0 XML → JSONL 构建（02 标准入口，优先于 01）

- [x] `src/parse_pmc.py` — 修正版 JATS 解析（title / pub_year / pub_date / pmid / abstract）
- [x] `src/build_jsonl.py` + `scripts/build_jsonl.sh` — 批量扫描 XML、写 jsonl
- [x] 验证期 100 篇已重生成至 `data/processed/sample.jsonl`
- [x] `build_jsonl.py --slim` / `--skip-no-abstract` — 全量 slim 与解析阶段清洗
- [x] `src/pmc_index.py` + `scripts/build_pmcid_index.sh` — pmcid 路径索引
- [x] `scripts/build_full_slim.sh` — 全量一键 slim 构建
- [x] `load_pipeline` 支持 slim 列集（无 body 时用 `n_chars_body`）
- [ ] 全量期：外接盘跑通 `build_pmcid_index` + `build_full_slim` + notebook

### 2.1 实现要点（JSONL → Dataset）

- [ ] **路径**：`DATA_ROOT = os.environ.get("MED_RAG_DATA_ROOT", PROJECT_DIR + "/data")`；`SAMPLE_JSONL = f"{DATA_ROOT}/processed/sample.jsonl"`
- [ ] **加载**：`datasets.load_dataset("json", data_files=SAMPLE_JSONL, split="train")`  
  或 `pandas.read_json(..., lines=True)` + 转 `Dataset`（二选一，notebook 中对比说明即可）
- [ ] **统一 schema**：列名、类型、`pmcid` 唯一性检查
- [ ] **派生列**（便于后续章节）：
  - `has_abstract`, `has_body`, `title_len`, `abstract_char_len`
  - `retrieval_text` = `title + "\n" + abstract`（检索单元初稿）
- [ ] **基础 facts 函数**：`describe_dataset()` → 行数、列、内存、样例行

### 2.2 全量数据（代码验证通过后 · 外接硬盘）

> 与「是否扩大样本」无关：目标是 **全库** 评估。主表用 **slim jsonl**，正文以 **XML 为唯一全文副本**。

- [ ] 外接硬盘就绪，`MED_RAG_DATA_ROOT` 指向 `<盘>/med-rag-pmc`
- [ ] 下载脚本：列出 `oa_comm/xml/` → 批次下载到 `raw/` → 解压 `extracted/`
- [ ] `./scripts/build_pmcid_index.sh`（`PMC_XML_ROOT=$MED_RAG_DATA_ROOT/extracted`）
- [ ] `./scripts/build_full_slim.sh` → `oa_comm_slim.jsonl`（`--slim --skip-no-abstract`）
- [ ] `export MED_RAG_JSONL=.../oa_comm_slim.jsonl`；notebook **不改分析逻辑**，仅切换路径
- [ ] body token 分位数：抽样 N 篇 + `pmc_index.load_body_for_pmcid`，或单独流式统计脚本
- [ ] 说明文档：**「100 篇验证」vs「全量统计」**；注明 slim 形态与清洗在 parse 阶段完成

### 2.3 验收

- [ ] 一行代码/一个 cell 可加载全量分析数据
- [ ] 打印数据集规模与字段列表，与说明文档「数据集事实」一致

---

## 阶段 3：数据结构分析（任务 §1）

### 3.1 字段完整性

- [x] 各字段非空率 / 缺失率表（`pmcid, title, abstract, body, journal, pub_year/pmid`）
- [x] **`abstract` 缺失率 > 1%？** → **丢弃** 3 篇，输出 `sample_clean.jsonl`（97 篇）
- [x] `title` 异常长 → 02 `parse_pmc` 修复后 0 篇 >500 字符

### 3.2 基础质量

- [x] 极短 `abstract` / `body` 计数与样例
- [x] 编码异常、乱码、大量 HTML/XML 残留（正则抽检）
- [x] 重复 `pmcid` 检查

### 3.3 关键字段与元数据价值

- [x] `journal`：Top-N 期刊、是否适合「按期刊过滤」
- [x] `pub_year` / `pub_date`：年份分布；能否支持「近 5 年」类过滤（需定义 cutoff）
- [ ] `pmid`：补字段后验证链接可打开比例（覆盖率 93% 已统计；链接实测可阶段 7 补）
- [x] 结论写入说明文档：**能否实现「检索近 5 年《Nature》上的文献」**——若缺精确日期或 journal 标准化不足，如实写限制

### 3.4 产出

- [x] `outputs/tables/field_completeness.csv`
- [x] notebook §3 留档 + 说明文档 §「数据集事实」「字段情况」

### 进度记录 · 2026-05-15

**本日完成至阶段 3（任务书 §1）**，阶段 4 留明日。

| 类别 | 内容 |
|---|---|
| 工程 | 目录骨架；VS Code + `med-rag-verify`；notebook【前置 1/2】【前置 2/2】 |
| 数据流 | `parse_pmc.py` + `build_jsonl.sh`；100 篇 `sample.jsonl` 由 02 parser 重生成（对齐原 pmcid） |
| 质量修复 | 01 XPath 污染已修：title>500 为 0；pub_year / pmid / pub_date 正常（见「数据质量问题」） |
| §0–§2 | `load_pipeline` 加载、schema 校验、`ds` / `df` |
| **§3** | 完整性表、丢弃 3 篇无 abstract → `sample_clean.jsonl`（97 篇）；`quality_flags` / 期刊·年份表 |
| 说明文档 | `docs/RAG数据分析与设计说明.md` §2–§3 要点已填 |
| 明日预留 | `domain_analysis.py` + notebook §4 框架（未实现业务逻辑） |

---

## 阶段 4：领域内容理解（任务 §2）

> 代码：`src/domain_analysis.py`；notebook `§4.1`–`§4.3`。

### 今日第一步（按顺序）

1. 【前置 1/2】【前置 2/2】
2. 运行 notebook **§4.1**（分层抽样 → `stratified_*.md`）
3. 运行 **§4.2**（IMRaD / 缩写 / 高频词 → `outputs/tables/*.csv`）
4. 阅读样例，补全 **§4.3** 同义表述 → 同步 `docs/RAG数据分析与设计说明.md` §4

### 4.1 分层抽样（按 token）

- [x] 用 **`all-MiniLM-L6-v2` tokenizer** 对 **`abstract`** 计 token
- [x] 按 **P33 / P66** 分 short / medium / long（验证期：≈309 / ≈399 tokens）
- [x] 每桶抽 **5 篇** → `outputs/samples/stratified_{short,medium,long}.md`

### 4.2 结构与术语（人工 + 简单统计）

- [x] **IMRaD** 关键词出现率 → `imrad_keyword_rate.csv`
- [x] **缩写** 密度 → `abbrev_density.csv`
- [ ] **同义表述**：读样例后于 notebook §4.3 填 1~2 例
- [x] （可选）高频词 Top-30 → `abstract_top_terms.csv`

### 4.3 产出

- [x] 说明文档 §「领域语言特性」要点（自动统计 + 待补同义表述）
- [ ] notebook §4.3 人工表「同义表述」两行

### 进度记录 · 阶段 4

| 类别 | 内容 |
|---|---|
| 代码 | `domain_analysis.py` 全函数 + `run_domain_pipeline` |
| §4.1 | P33≈309 / P66≈399 tokens；三桶各 5 篇样例 md |
| §4.2 | Results 关键词 ~55%；缩写 ~3.8/百词；Top 词 patients/study/… |
| 同义表述 | 可在 §4.3 / 说明文档 §4.3 续补 1–2 例（非阻塞阶段 5/6） |

---

## 阶段 5：文本特征量化分析（任务 §3）

### 5.1 Token 长度（核心）

对以下文本分别统计 **token 数**（同一 tokenizer，`src/token_stats.py`）：

- [x] `title`
- [x] `abstract`
- [x] `title + abstract`（拟检索单元）
- [x] `body`（无 `body` 列时记 0，全量 slim 期需回 XML 另算）

输出：**均值、P50、P75、P95、P99、max** → `outputs/tables/token_percentiles.csv`

### 5.2 与 embedding 上限 512 对照

- [x] 已根据 `token_percentiles.csv` 与 97 篇实测写入 `docs/RAG数据分析与设计说明.md` **§5.2（定稿）**
- [x] 实测 **P95(title+abstract)≈617 > 512**：**不能**对全部篇目采用「整块不切分」；约 **85%** 单篇 ≤512，**约 14%** 需截断或滑动窗口
- [x] **P99(title+abstract)≈1009 > 512**：长尾明显，阶段 6 需写明滑动窗口参数依据
- [x] **body** 本批 **100%** 超 512、P95 约 2 万 tokens → **正文必须 chunk**，与摘要策略分开

### 5.3 可视化

- [x] `outputs/figures/token_dist_abstract.png`（ECDF：abstract + title+abstract）
- [x] 表：`outputs/tables/token_percentiles.csv`

### 进度记录 · 阶段 5（收尾 · 2026-05-19）

| 类别 | 内容 |
|---|---|
| 代码 | `src/token_stats.py` + notebook **§5** |
| 产出 | `token_percentiles.csv`、`token_dist_abstract.png` |
| 文档 | `docs/RAG数据分析与设计说明.md` §5.1~5.2 定稿；**检索单元**定为 **title+abstract**（与 `load_pipeline.retrieval_text` 一致） |
| 依赖 | `02 数据处理/requirements.txt`（matplotlib / transformers 等）已在 `med-rag-verify` 安装 |
| 下一步 | 阶段 6：基于上表写 **分割策略总表** + 可选 LangChain demo |

---

## 阶段 6：制定文本分割策略（任务 §4）

> 本阶段输出 **决策 + 理由**，可在 notebook 用 LangChain `RecursiveCharacterTextSplitter` **演示 2~3 条**，不做全库切分。  
> **输入依据**：阶段 5 已测得 title+abstract 的 P95≈617、P99≈1009，>512 约 **14.4%**；body **100%** 超 512。

### 6.1 决策表（写入说明文档）

- [x] 定稿表已写入 `docs/RAG数据分析与设计说明.md` **§6**

| 条件（验证期 97 篇） | 策略 | 工具/参数 |
|---|---|---|
| title+abstract **≤512**（83 篇） | **单 chunk** | 不分割 |
| title+abstract **>512**（14 篇） | **滑动窗口** | `RecursiveCharacterTextSplitter` 400 / overlap 80 |
| 显式 IMRaD 小标题极少 | **备选**章节切分 | 本批不默认 |
| 无 abstract | **丢弃** | 阶段 3 / 全量 skip 列表 |

### 6.2 正文 `body` 单独策略

- [x] **一律 sliding window**：`chunk_size=512`, `overlap=80`（`chunk_body_text`）
- [x] 与摘要 pipeline 分离；首轮 RAG 可不索引 body

### 6.3 清洗与分割联动

- [x] 缺失 `abstract`：**丢弃**并记录（97 篇进 `df_clean`）
- [x] 低质量篇：§3.2 **flag 标记**；验证期 short_abstract=0；**暂不排除**，全量复核

### 6.4 验收

- [x] 说明文档 §6 定稿 + `chunk_strategy_summary.csv` / `chunk_strategy_config.json`
- [x] notebook **§6.1–§6.2**：`print_strategy_banner` + 长尾/body demo

### 进度记录 · 阶段 6（2026-05-19）

| 类别 | 内容 |
|---|---|
| 代码 | `src/chunk_strategy.py` |
| 验证 | 97 篇：**single=83, multi=14** |
| 产出 | `outputs/tables/chunk_strategy_summary.csv`, `chunk_strategy_config.json` |
| 全量 | 读 config json → ingest；见说明文档 §6.4 |

---

## 阶段 7：交付整理

### 7.1 《RAG 数据分析与设计说明》大纲

```markdown
1. 概述与数据范围（oa_comm、样本量、来源）
2. 数据集事实（大小、字段、缺失、清洗后规模）
3. 数据结构分析与清洗策略
4. 领域语言特性（抽样、IMRaD、术语、可选词频）
5. 文本长度分布（字符 + token，P95/P99）
6. 分割策略及原因（摘要 vs 正文）
7. 元数据过滤可行性（journal、年份、pmid 链接）
8. 对后续 RAG 开发的建议（不含实现）
9. 附录：图表索引、复现方式（notebook 路径）
```

### 7.2 交付清单

- [ ] `docs/RAG数据分析与设计说明.md`
- [ ] `notebooks/med-data-EDA.ipynb`（可复现全部分析）
- [ ] `outputs/` 下图表与 CSV
- [ ] `requirements.txt`（本阶段增补记录）
- [ ] （可选）`src/load_pipeline.py` 若从 notebook 抽离

### 7.3 自检 Checklist

- [ ] 任务书 §1~§4 均有对应章节，且结论有**数据支撑**（非空泛）
- [ ] 明确写出 **abstract 缺失率** 与是否 >1%
- [ ] 明确写出 **P95/P99 token** 与 512 上限关系
- [ ] 分割策略可被执行（参数具体）
- [ ] 未混入 RAG/向量库/LLM 实现（最多 tokenizer demo）

---

## 工作方式约定

1. **先 notebook 跑通、再写说明文档**：图表从 `outputs/` 贴入 md，避免手写数字不一致。
2. **与 01 解耦**：01 只作数据源与 parser 来源，不在 01 目录堆 02 的分析产物。
3. **VS Code + Jupyter**：直接选 conda 内核跑 notebook；不用 Cursor Jupyter，也不依赖 01 的 `start_jupyter.sh`。
4. **小步提交**：每完成阶段 3~6 中的一节，在下方「进度跟踪」记一行。

---

## 与暂缓的 RAG 工程关系

| 本阶段产出 | 未来 `** LangChain_RAG` / RAG 阶段如何使用 |
|---|---|
| 清洗规则 | `filter` / 建库前预处理 |
| token 分位数 | 定 `chunk_size` / `overlap` |
| 分割策略表 | 实现 `RecursiveCharacterTextSplitter` 或章节切分 |
| 元数据字段 | Chroma `metadata` + 检索过滤 |
| 说明文档 | 项目设计依据、答辩/汇报材料 |

---

## 学习资源（按需）

- Hugging Face `datasets` 加载 JSONL：https://huggingface.co/docs/datasets/loading
- LangChain Text Splitters：https://python.langchain.com/docs/how_to/recursive_text_splitter/
- Sentence-Transformers 模型卡片：`sentence-transformers/all-MiniLM-L6-v2`（max seq 512）
- PMC OA Bulk：https://www.ncbi.nlm.nih.gov/pmc/tools/openftlist/

---

## 项目进度汇总

| 日期 | 完成阶段 | 备注 |
| --- | --- | --- |
| 2026-05-15 | 1（部分） | 目录框架；`sample.jsonl` 自 01 复制；VS Code 约定 |
| 2026-05-15 | 0 + 2 | `med-data-EDA.ipynb` §0/§2；`load_pipeline.py` 跑通（100 篇，abstract 缺失率 3%） |
| 2026-05-15 | — | 数据质量诊断：title/pub_year XPath 污染、abstract 3% 缺失；见 `笔记/02笔记.ipynb` |
| 2026-05-15 | 2.0 | `parse_pmc.py` + `build_jsonl.sh`；100 篇 sample 已用 02 parser 重生成 |
| 2026-05-15 | 3 ✅ | §3 完成：完整性/质量/元数据表；清洗 97 篇；阶段 3 验收 |
| 2026-05-19 | 5 ✅ + 6 ✅ | token 分位数 + ECDF；切块 **83/14**；`chunk_strategy_config.json` |
| **明日** | **阶段 B** | 外接盘 + 全量下载 + slim + 策略抽样验证（见下节） |

> 按日明细写在**各阶段章节末尾**的「进度记录」中（例如阶段 3 完成后写在阶段 3 与阶段 4 之间）。  
> 此处追加一页总览表。

---

## 后续工作 · 阶段 B：外接盘 + 全量数据 + 策略验证（已完成）

> **目标**：外接盘跑通 **下载 → 解压 → slim jsonl → 索引 → 抽样验证**，确认小样本策略可推广。详见上文「全量期工程约定」。  
> **外接盘（已定）**：`/Volumes/Lexar/med-llm-rag-datasets` — 2026-05-19 已验证挂载、可写；`raw/` `extracted/` `processed/stats/` 骨架已建好。

### 0. 开工前检查

- [x] 外接盘挂载：`/Volumes/Lexar/med-llm-rag-datasets`（可用 **~1.2 TiB**，2026-05-19 验证可写）
- [ ] 内核 **`med-rag-verify`**；`pip install -r 02 数据处理/requirements.txt` 已就绪
- [ ] 网络稳定（`oa_comm` 下载可分批，不必首日下满）

### 1. 环境变量（每次新开终端）

**推荐**（已写好脚本）：

```bash
cd "02 数据处理"
source ./scripts/setup_full_data_env.sh
```

等价于：

```bash
export MED_RAG_DATA_ROOT=/Volumes/Lexar/med-llm-rag-datasets
export PMC_XML_ROOT="$MED_RAG_DATA_ROOT/extracted"
export MED_RAG_JSONL="$MED_RAG_DATA_ROOT/processed/oa_comm_slim.jsonl"
# 目录骨架已创建：raw/ extracted/ processed/stats/
```

### 2. 下载与解压

- [ ] [PMC OA FTP](https://www.ncbi.nlm.nih.gov/pmc/tools/ftp/) → `deprecated/oa_bulk/oa_comm/xml/` 目录清单（**非**旧 `oa_comm/xml/file_list.txt`）
- [ ] 下载到 `$MED_RAG_DATA_ROOT/raw/`，解压到 `$PMC_XML_ROOT`
- [ ] **建议**：先 1 个小包试解压，再扩大批次（时间紧可先 1~5 万篇做验证）

### 3. 构建（与验证期同一规则）

```bash
cd "02 数据处理"
./scripts/build_pmcid_index.sh
./scripts/build_full_slim.sh
```

产出：`oa_comm_slim.jsonl`、`skipped_no_abstract.txt`、`pmcid_index.jsonl`。

### 4. 策略验证（不必先 embedding 全库）

| # | 项 | 通过参考（验证期 97 篇） |
|---|-----|-------------------------|
| 1 | abstract 缺失率 | `skipped` 占比 ~3% 量级 |
| 2 | P95 / >512（抽样或流式） | P95(retrieval) ~600 左右；>512 ~14% |
| 3 | single / multi 切块（抽样） | ~83% / ~14% |
| 4 | 参数 | 沿用 `chunk_strategy_config.json`（400/80；body 512/80） |
| 5 | body（可选，抽 100 篇 XML） | 多篇多块 |

偏离时写说明文档「全量 vs 验证期」对比，再决定是否调参。

### 5. 明日不做

- ❌ 全库 Chroma / embedding
- ❌ 全库 body 进 jsonl
- ❌ 大改 02 代码（除非全量 bug）

### 6. 文档

- [ ] `docs/RAG数据分析与设计说明.md` 增「全量验证」小节
- [ ] notebook **`med-data-EDA-partB.ipynb`（B0～B6）** 跑通：下载 → 解压删包 → slim → 抽样对比

> 阶段 B 已写入 notebook 文末，辅助模块 `src/full_scale_pipeline.py`。


自用提交：
git add -A
git status
git commit -m "02: 阶段6根据小规模数据集拟定策略,待外接盘后全量数据集验证可行性"
git push
---

## 📊 第二阶段汇报摘要（2026-05-27 已完成）

### 完成情况一览

| 子任务 | 状态 | 关键证据 |
|---|---|---|
| 数据加载 pipeline | ✅ | `src/load_pipeline.py` + `build_jsonl.py` + 分批处理支持断点续传 |
| 数据结构分析（§1） | ✅ | 字段完整性、清洗策略、元数据可用性评估 |
| 领域内容理解（§2） | ✅ | 分层抽样、IMRaD 结构、术语密度统计 |
| Token 长度分析（§3） | ✅ | P95=612 tokens，约 14% 超 512 需分割 |
| 分割策略设计（§4） | ✅ | 单块 86% / 滑动窗口 14%；参数 400/80 |
| 全量数据处理 | ✅ | **4,557,627 篇** slim JSONL（8.9 GB） |
| 策略验证 | ✅ | 全量与验证期一致，参数无需调整 |
| 正式文档 | ✅ | `docs/RAG数据分析与设计说明.md` 定稿 |

### 核心数据

| 指标 | 验证期 (97篇) | 全量期 (4,557,627篇) |
|------|--------------|---------------------|
| P95 retrieval tokens | 617 | 612 |
| >512 占比 | 14.4% | 13.7% |
| 单块占比 | 85.6% | 86.4% |
| abstract 丢弃率 | 3% | 8.74% |

### 核心交付物

| 类别 | 文件 / 目录 | 说明 |
|---|---|---|
| 主数据文件 | `E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl` | 4,557,627 行，8.9 GB |
| 正式文档 | `docs/RAG数据分析与设计说明.md` | 任务书要求的交付产物 |
| 分割策略配置 | `outputs/tables/chunk_strategy_config.json` | 供第三阶段直接使用 |
| 验证期 notebook | `notebooks/med-data-EDA-partA.ipynb` | §1~§6 定稿（只读） |
| 全量期 notebook | `notebooks/med-data-EDA-partB.ipynb` | B0~B6 全流程 |
| 数据 pipeline | `src/full_scale_pipeline.py` | 分批处理 + 断点续传 |

### 下一步

第三阶段可以直接读取 `oa_comm_slim.jsonl`，按已定策略进行文本分割。
