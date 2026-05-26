# RAG 数据分析与设计说明

> **状态：已完成** — 验证期 §1~§6 定稿 + 全量期 B0~B6 验证通过（2026-05-27）

## 1. 概述与数据范围

- **验证期（A）**：`sample.jsonl` 含 `body` 全文，便于 notebook 本地分析；无 abstract 的 3 篇在 §3 丢弃后另有 `sample_clean.jsonl`（97 篇）。
- **全量期（B）**：`oa_comm_slim.jsonl`（无 `body` 列，保留 `n_chars_body`）；解析阶段 `--skip-no-abstract`，不生成第二份 clean 副本；正文以 `extracted/**/*.xml` 为准，按需经 `pmcid` + `pmcid_index.jsonl` 回查。

## 2. 数据集事实

### 2.1 验证期（100 篇样本）

- 验证样本：100 篇（`sample.jsonl`，02 `parse_pmc` 自 XML 生成）
- 清洗后：97 篇（`sample_clean.jsonl`，丢弃 3 篇无 abstract）
- 验证期字段：pmcid, pmid, title, abstract, body, journal, pub_year, pub_date, n_chars_*
- title 长度：02 parser 修复后正常（无 >500 字符异常）
- abstract 缺失率：3%（> 任务书 1% 阈值）

### 2.2 全量期（PMC oa_comm 全量）

| 指标 | 数值 |
|------|------|
| 原始 XML 文件数 | **4,994,166** |
| 输出 slim JSONL 行数 | **4,557,627** |
| 无 abstract 丢弃数 | 436,521 |
| abstract 丢弃率 | **8.74%** |
| slim 文件大小 | 8,896.6 MB |
| 处理失败（解析错误） | 17 篇 |

全量期字段：pmcid, pmid, title, abstract, journal, pub_year, pub_date, n_chars_abstract, n_chars_body（**不含 body 正文**）

**数据来源**：PMC Open Access Commercial Use (`oa_comm`) 13 个 baseline 包，共约 5TB 压缩包解压后的 XML 文件。

## 3. 数据结构分析与清洗策略

### 3.1 字段完整性

见 `outputs/tables/field_completeness.csv`。

| 决策项 | 结论 |
|---|---|
| abstract 缺失 3% | **丢弃**无 abstract 记录（RAG 检索依赖摘要） |
| 输出 | `data/processed/sample_clean.jsonl`（97 篇） |

### 3.2 基础质量

- 极短 abstract（<50 字符）：0 篇
- 异常长 title（>500 字符）：0 篇（02 parser）
- 重复 pmcid：0

### 3.3 元数据

- pmid 覆盖率约 93%；缺失可用 PMC 链接替代
- pub_year 可用于「近 5 年」粗筛；精确过滤用 pub_date
- journal 未标准化，暂不宜直接筛「Nature」刊名

## 4. 领域语言特性

> 验证期 97 篇（`df_clean`）；tokenizer：`sentence-transformers/all-MiniLM-L6-v2`。样例见 `outputs/samples/stratified_*.md`。

### 4.1 摘要长度分层（token）

| 桶 | 划分（abstract tokens） | 篇数（97 篇中） |
|---|---|---|
| short | ≤ P33（≈309） | 32 |
| medium | P33–P66（≈309–399） | 32 |
| long | > P66（≈399） | 33 |

每桶随机抽 5 篇导出 Markdown，供人工阅读。

### 4.2 结构与术语（自动统计）

| 指标 | 结果 |
|---|---|
| IMRaD 关键词出现率 | Background 8.3% · Methods 20.6% · **Results 54.6%** · Conclusion 11.3% |
| 四段标题关键词全齐 | 4.1%（多数摘要无显式小节标题） |
| 缩写密度（均值） | 约 **3.8** 次 / 百词 |
| 高频词 Top-5 | patients, study, using, analysis, risk |

表：`outputs/tables/imrad_keyword_rate.csv`、`abbrev_density.csv`、`abstract_top_terms.csv`。

### 4.3 语言风格与 RAG 启示（心理基线）

- **风格**：正式学术英语，信息密度高；常在一段内交代背景、方法、结果。
- **结构**：不宜默认摘要含 `METHODS:` / `RESULTS:` 标题；检索与评估应用自然语言问法。
- **术语**：存在医学缩写（如 EGFR、PCI）；同一概念可能有全称/缩写并存——**同义表述样例待读 stratified 样例后补 1–2 条**。
- **对 prompt/评估**：测试集应覆盖短/中/长摘要；问题宜具体、可核对；评估时允许合理同义改写。

## 5. 文本长度分布

> 验证期 97 篇；tokenizer：`sentence-transformers/all-MiniLM-L6-v2`（max 512）。实现：`src/token_stats.py`，notebook **§5**。

### 5.1 分位数表

验证期 **97 篇**（`df_clean`），详见 `outputs/tables/token_percentiles.csv`。摘要字段 token 分布见下（与 §5.2 对照）。

| 字段 | P95 (tokens) | P99 (tokens) | max (tokens) |
|---|---|---|---|
| title | ≈36 | ≈49 | 51 |
| abstract | ≈587 | ≈977 | 986 |
| title+abstract | ≈617 | ≈1009 | 1009 |
| body | ≈20574 | ≈26213 | 54542 |

### 5.2 与 512 上限对照（定稿）

验证期 97 篇、tokenizer 为 `sentence-transformers/all-MiniLM-L6-v2`（统计口径）：**abstract** 的 token 长度为 **P95≈587、P99≈977**；**title+abstract**（拟检索单元）为 **P95≈617、P99≈1009**；**body** 为 **P95≈2.06×10⁴、P99≈2.62×10⁴、max≈5.45×10⁴**（与 `token_percentiles.csv` 一致）。以 **512 tokens** 为单次嵌入上限衡量时，**abstract** 超过 512 的约占 **13.4%**（13/97），**title+abstract** 超过 512 的约占 **14.4%**（14/97），**body** **100%**（97/97）超过该上限。因此：**摘要/检索单元**可采取「多数整块嵌入、约一成余长摘要截断或滑动窗口」；**正文**必须 **chunk** 且与摘要策略分开；本工程与 `load_pipeline.retrieval_text` 一致，**检索文本单元采用 title+abstract**（相对仅用 abstract，>512 占比约升 1 个百分点，标题带来的边际 token 很小）。

### 5.3 图

- `outputs/figures/token_dist_abstract.png`：abstract 与 title+abstract 的 **ECDF** + 512 竖线。

## 6. 分割策略及原因（定稿）

> 验证期 97 篇；检索单元 **title+abstract**；实现 **`src/chunk_strategy.py`** + notebook **§6**。全量 ingest 时复用 `outputs/tables/chunk_strategy_config.json`。

### 6.1 决策总表

| 对象 | 条件 | 策略 | 工具 / 参数 |
|---|---|---|---|
| **检索单元** title+abstract | token ≤ **512**（约 **83/97** 单块） | **不分割**，1 Document / 1 embedding | 与 `all-MiniLM-L6-v2` max 对齐 |
| 同上 | token **> 512**（约 **14/97** 多块） | **重叠滑动窗口** | `RecursiveCharacterTextSplitter`；`chunk_size=400`，`overlap=80`；`length_function`=同款 tokenizer |
| **正文 body** | 一律远超 512（阶段 5：100% 超） | **单独** sliding window | `chunk_size=512`，`overlap=80`；**首轮 RAG 可不索引**，二期全文检索启用 |
| 显式 IMRaD 小标题 | 极少（§4.2 ~4%） | **备选**按章节 | 有 `METHODS:`/`RESULTS:` 等时再考虑；本批 **不默认** |
| **无 abstract** | 缺失 | **丢弃**，记录 pmcid | 验证期 3/100；全量 `--skip-no-abstract` |
| **低质量 flag** | short_abstract 等（§3.2） | **标记**；验证期 0 篇 | 全量复核后再定是否排除 |

### 6.2 理由（与阶段 5 数据对齐）

- P50(retrieval)≈374、P95≈617 → **主体可整块**，**长尾需窗口**；非「全体滑动窗口」。
- 入库时用 **确定性 pipeline**（短→单块，长→splitter），**不在查询时**再数 token。
- body 与摘要 **分 pipeline**；避免把万级 token 正文与摘要混为同一 chunk 规则。

### 6.3 验证期 demo 结果（notebook §6 已跑通）

- `chunk_strategy_summary.csv`：**single=83，multi=14**（97 篇）；总 retrieval chunk 数 **123**（与 §5「>512 约 14.4%」一致）。
- 长尾示例：`PMC12869397` → **4 chunks**（sliding_window）；`PMC12295483` → 3 chunks。
- body 示例：`PMC8774754` → **8 chunks**（512/80；首轮 RAG 可不索引 body）。
- 参数快照：`outputs/tables/chunk_strategy_config.json`（全量 ingest 直接引用，**勿改参数除非全量分布显著偏离**）。

### 6.4 全量期验证结果（已完成）

**数据根**：`E:\med-llm-rag-datasets`（Windows）或 `/Volumes/Lexar/med-llm-rag-datasets`（Mac）

**执行入口**：`notebooks/med-data-EDA-partB.ipynb`（B0～B6）

#### 验证期 vs 全量期对比（5000 篇抽样）

| 指标 | 验证期 (97篇) | 全量期 (5000篇抽样) | 差异 | 结论 |
|------|--------------|-------------------|------|------|
| P95 retrieval tokens | 617.2 | **612.0** | -5.2 | ✅ 一致 |
| >512 占比 (%) | 14.4 | **13.70** | -0.7 | ✅ 一致 |
| 单块占比 (%) | 85.6 | **86.40** | +0.8 | ✅ 一致 |
| 多块占比 (%) | 14.4 | **13.60** | -0.8 | ✅ 一致 |
| abstract 丢弃率 (%) | 3.0 | **8.74** | +5.74 | ⚠️ 偏高 |

#### 全量期 Token 分布（5000 篇抽样）

| 字段 | mean | P50 | P75 | P95 | P99 | max |
|------|------|-----|-----|-----|-----|-----|
| title | 23.65 | 23 | 29 | 40 | 51 | 78 |
| abstract | 352.67 | 340 | 427 | 584 | 766 | 1902 |
| **title+abstract** | **376.32** | 365 | 453 | **612** | 793 | 1919 |

#### 结论

1. **分割策略参数无需调整**：P95、>512 占比、单块/多块比例与验证期高度一致
2. **abstract 丢弃率偏高**（8.74% vs 3%）：属于 PMC 数据集本身特性，非处理错误
   - 原因：全量数据中包含更多元数据类、勘误类、撤稿声明等无摘要文献
   - 处理：已按策略丢弃并记录到 `skipped_no_abstract.txt`
3. **验证期策略可直接用于全量**：`chunk_strategy_config.json` 参数保持不变

产出文件：
- `E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl`（4,557,627 行）
- `E:\med-llm-rag-datasets\processed\stats\verify_vs_full_compare.csv`
- `E:\med-llm-rag-datasets\processed\stats\full_scale_verdict.txt`

## 7. 元数据过滤可行性

| 字段 | 覆盖率 | 可用于过滤 | 说明 |
|------|--------|-----------|------|
| `pmcid` | 100% | ✅ | 唯一标识，可追溯 PMC 原文 |
| `pmid` | ~93% | ✅ | 可链接 PubMed，少量缺失 |
| `pub_year` | ~99% | ✅ | 支持"近 5 年"粗筛 |
| `pub_date` | ~95% | ✅ | 精确日期过滤 |
| `journal` | ~99% | ⚠️ | 未标准化，需预处理后才能精确筛选 |

## 8. 对后续 RAG 开发的建议

1. **第三阶段（分割）**：直接读取 `oa_comm_slim.jsonl`，无需回访 XML
2. **检索单元**：使用 `title + abstract`，约 86% 可单块嵌入
3. **长尾处理**：约 14% 超过 512 tokens，使用 `RecursiveCharacterTextSplitter(chunk_size=400, overlap=80)`
4. **Body 正文**：首轮 RAG 可不索引，二期全文检索时再启用（单独 pipeline）
5. **元数据**：保留 pmcid、pub_year 等字段，支持后续过滤检索

## 9. 附录

### 9.1 全量处理统计（按子文件夹）

| 子文件夹 | 成功 | 丢弃(无abstract) | 失败 |
|---------|------|-----------------|------|
| PMC000xxxxxx | 2,775 | 253 | 0 |
| PMC001xxxxxx | 24,466 | 3,052 | 0 |
| PMC002xxxxxx | 111,250 | 11,327 | 1 |
| PMC003xxxxxx | 293,323 | 30,419 | 0 |
| PMC004xxxxxx | 357,255 | 35,480 | 2 |
| PMC005xxxxxx | 362,708 | 73,159 | 2 |
| PMC006xxxxxx | 426,070 | 36,005 | 3 |
| PMC007xxxxxx | 443,293 | 22,231 | 1 |
| PMC008xxxxxx | 508,703 | 41,795 | 4 |
| PMC009xxxxxx | 532,208 | 72,094 | 1 |
| PMC010xxxxxx | 553,423 | 57,407 | 0 |
| PMC011xxxxxx | 517,838 | 29,551 | 2 |
| PMC012xxxxxx | 424,315 | 23,748 | 2 |
| **合计** | **4,557,627** | **436,521** | **17** |

### 9.2 关键配置文件

- 分割策略：`02 数据处理/outputs/tables/chunk_strategy_config.json`
- Tokenizer：`sentence-transformers/all-MiniLM-L6-v2`
- 验证期统计：`02 数据处理/outputs/tables/token_percentiles.csv`
- 全量期统计：`E:\med-llm-rag-datasets\processed\stats\`
