# RAG 数据分析与设计说明

> 状态：骨架（阶段 7 定稿）。验证期基于 100 篇；全量结论待外接硬盘跑完后补充。

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

## 5. 文本长度分布

## 6. 分割策略及原因

## 7. 元数据过滤可行性

## 8. 对后续 RAG 开发的建议

## 9. 附录
