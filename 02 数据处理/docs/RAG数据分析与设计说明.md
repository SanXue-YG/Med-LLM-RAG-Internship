# RAG 数据分析与设计说明

> 状态：撰写中。验证期 **§1~§5** 已定稿（100 篇 / 清洗后 97 篇）；**§6 分割策略** 待阶段 6 补全；全量结论待外接硬盘后补充。

## 1. 概述与数据范围

- **验证期（A）**：`sample.jsonl` 含 `body` 全文，便于 notebook 本地分析；无 abstract 的 3 篇在 §3 丢弃后另有 `sample_clean.jsonl`（97 篇）。
- **全量期（B）**：`oa_comm_slim.jsonl`（无 `body` 列，保留 `n_chars_body`）；解析阶段 `--skip-no-abstract`，不生成第二份 clean 副本；正文以 `extracted/**/*.xml` 为准，按需经 `pmcid` + `pmcid_index.jsonl` 回查。

## 2. 数据集事实

- 验证样本：100 篇（`sample.jsonl`，02 `parse_pmc` 自 XML 生成）
- 清洗后：97 篇（`sample_clean.jsonl`，丢弃 3 篇无 abstract；**仅验证期**）
- 验证期字段：pmcid, pmid, title, abstract, body, journal, pub_year, pub_date, n_chars_*
- 全量期字段（计划）：同上但 **不含 body 字符串**；见 `schedule.md` 阶段 B
- title 长度：02 parser 修复后正常（无 >500 字符异常）
- abstract 缺失率：3%（> 任务书 1% 阈值）

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

## 6. 分割策略及原因

> **待阶段 6 定稿**。以下为与阶段 5 数据对齐的**初稿决策表**（验证期 97 篇；检索单元 = **title+abstract**）。

| 条件 | 策略 | 工具/参数（建议） |
|---|---|---|
| 约 85% 篇 title+abstract ≤512（P50≈374） | 主体：单 chunk 整块嵌入 | 与 `all-MiniLM-L6-v2` max 512 对齐 |
| ~14% 篇 >512（P95≈617，P99≈1009） | 长尾：截断或重叠滑动窗口 | `RecursiveCharacterTextSplitter`；`chunk_size=300~500`，`overlap=50~100` |
| 摘要少显式章节标题（见 §4.2） | 优先滑动窗口；按章节切分作备选 | 见阶段 6 notebook demo |

**正文 body**：本批 **100%** 超 512，P95 约 2×10⁴ tokens → **必须**与摘要分开做 **滑动窗口 chunk**；具体 `chunk_size`/`overlap` 可引用 body 分位数在阶段 6 写死。

## 7. 元数据过滤可行性

## 8. 对后续 RAG 开发的建议

## 9. 附录
