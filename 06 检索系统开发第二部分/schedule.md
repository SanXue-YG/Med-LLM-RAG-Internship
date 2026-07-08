# 06 检索系统开发第二部分 — 执行计划

> **状态：✅ 已完成（阶段 0–5；notebook C0–C12）**
>
> **本阶段范围（任务书）**：实现多路检索（向量 + BM25）→ 融合 → 重排序，并与 05 查询增强模块打通为完整检索流水线。
>
> **上游依赖**：
> - 05：`MedicalQueryEnhancer` / `EnhancedQuery`
> - 04：`DocumentEmbedder` / `ChromaIndexBuilder` + Chroma 库
> - 03：`oa_comm_chunks.jsonl`（BM25 语料来源，title+abstract chunk）
> - 02：`oa_comm_slim.jsonl`（重排 recency/authority 回查，`doc_id` → `pub_year` / `journal`）

---

## ⚠️ 验证范围说明（必读）

**本阶段全部 notebook 跑通、单元测试、`pipeline_eval.json` 等样例输出，均在「样本库」上完成，不是全量 PMC 语料。**

| 维度 | 本阶段实际使用（`mode="sample"`，默认） | 后续 LangChain RAG 生产应切换（`mode="full"`） |
|------|----------------------------------------|-----------------------------------------------|
| 向量库 | `04 .../data/chroma_db` · `pmc_oa_comm_sample` | **`04 .../data/chroma_db_full` · `pmc_oa_comm_full`**（6,107,296 条；D: 或 E: 备份） |
| BM25 语料 | `03 .../chunks_sample.jsonl`（**1,267** chunks） | **`E:\med-llm-rag-datasets\processed\oa_comm_chunks.jsonl`**（**6,107,296** chunks） |
| slim 元数据 | `06 .../data/oa_comm_slim.jsonl`（已本地化，4,557,627 篇） | 同上或 E: 权威源（recency/authority 已覆盖全库） |
| 代码入口 | `MODE = "sample"`（notebook C0）· `from_mode("sample")` | **`from_mode("full")`** · CLI `--mode full` |

**为何样本库结果不能代表最终 RAG 质量**：1,267 条仅为 03/04 验证子集，药名、年份、长尾 query 在样本中常缺失或偏旧（如 malaria after 2015 无 2015+ 篇）。链路正确性已在样本库证明；**检索召回与排序质量须在全量库上复评**。

**构建最终 RAG 系统时务必**：

1. 确认 D: `chroma_db_full` 或 E: `chroma_db_full` 可访问（04 阶段已建库）。
2. 确认 E: `oa_comm_chunks.jsonl` 可访问（BM25 全量建索引；首次 build 耗时长、内存需规划）。
3. 将 `RetrievalPipeline.from_mode("full")` / CLI `--mode full` 作为生产默认；样本模式仅用于开发调试。

---

## 任务书目标对照

| 任务书要求 | 本阶段交付 |
|------------|------------|
| 多路检索（MultiPathRetriever） | `src/multipath_retriever.py`：向量检索 + BM25 关键词检索 |
| BM25 构建与查询 | `src/bm25_index.py`：分词、建索引、`top_k` 返回 |
| 融合策略（simple / rrf / weighted） | `src/fusion.py`：统一融合接口 |
| 重排序器（可用 bge-reranker-base） | `src/reranker.py`：cross-encoder 打分与排序 |
| 多准则重排序（relevance/recency/authority） | `src/rerank_features.py`：年份/期刊特征与加权 |
| 与上周模块打通 | notebook + CLI：`query -> enhanced -> retrieve -> fuse -> rerank` |

---

## 关键约束与设计决策（启动前）

| 项 | 决策 | 说明 |
|----|------|------|
| 查询语言 | **英文优先** | 延续 05（老师已确认） |
| 向量模型 | **保持 04 口径**：`BAAI/bge-small-en-v1.5` | 避免向量空间不一致 |
| BGE 前缀 | 继续由 04 `encode_queries()` 统一添加 | 06 不重复拼接 |
| 年份/期刊信号 | **检索后特征重排**，不重建 04 索引 | 04 metadata 无 `pub_year/journal` |
| slim 回查路径 | **本阶段 `data/oa_comm_slim.jsonl`（优先）** | 自 E: 复制至本地，避免开发时依赖外接盘 |
| 语料来源 | BM25 首版用 `03 .../chunks_sample.jsonl` 验证，再切全量 | 降低首轮开发风险；**RAG 上线前必须切全量** |
| **本阶段验证规模** | **样本库 only**（1,267 chunks） | 见上文「验证范围说明」；非生产数据 |
| 融合默认策略 | `rrf`（主）+ `weighted`（备） | 学术检索场景稳定 |

---

## 数据路径（开发默认）

| 用途 | 路径 | 条数 / 体积 | Git | 说明 |
|------|------|-------------|-----|------|
| **slim 回查（RAG 活跃）** | `06 .../data/oa_comm_slim.jsonl` | 4,557,627 篇，~8.9 GB | ❌ | 自 E: 复制；`resolve_slim_path()` 优先读此路径 |
| slim 权威源（备份） | `E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl` | 同上 | ❌ | 本地缺失时回退 |
| BM25 样本语料 | `03 .../data/processed/chunks_sample.jsonl` | 1,267 chunks | ✅ | 首轮开发 |
| BM25 全量语料 | `E:\...\oa_comm_chunks.jsonl` | 6,107,296 chunks | ❌ | 全量 BM25 时再挂载 |
| Chroma 样本库 | `04 .../data/chroma_db` | 1,267 | ❌ | collection: `pmc_oa_comm_sample` |
| Chroma 全量库 | `04 .../data/chroma_db_full` | 6,107,296 | ❌ | collection: `pmc_oa_comm_full` |

**回查字段**：按候选 `doc_id`（= slim 中 `pmcid`）读取 `pub_year`、`journal` 等，供 `rerank_features.py` 计算 recency / authority。**不回查原始 XML**。

代码入口：`src/config.py` → `resolve_slim_path()` / `resolve_chunks_path()` / `resolve_chroma()`。

---

## 模块设计

### 目录结构（规划）

```text
06 检索系统开发第二部分/
├── 任务.txt
├── schedule.md                      # 本文件
├── requirements.txt                 # 新增 rank-bm25 / reranker 依赖
├── data/
│   └── oa_comm_slim.jsonl           # 02 slim 本地副本（~8.9 GB，.gitignore）
├── src/
│   ├── __init__.py
│   ├── bm25_index.py                # BM25 构建/查询
│   ├── multipath_retriever.py       # 向量 + 关键词双路召回
│   ├── fusion.py                    # simple / rrf / weighted
│   ├── reranker.py                  # BGE reranker 打分
│   ├── rerank_features.py           # recency / authority 特征
│   └── pipeline.py                  # 端到端检索流水线
├── notebooks/
│   └── retrieval-pipeline.ipynb     # C0-C8 演示与验证
├── scripts/
│   └── run_retrieval_eval.py        # CLI 评测入口
├── tests/
│   ├── test_bm25.py
│   ├── test_fusion.py
│   ├── test_reranker.py
│   └── test_pipeline.py
└── outputs/
    └── samples/
        ├── retrieval_compare.json
        └── rerank_examples.json
```

### 核心 API（草案）

```python
class MultiPathRetriever:
    def retrieve(
        self,
        query_info,                 # 05 EnhancedQuery
        top_k_vector: int = 20,
        top_k_keyword: int = 20,
        fusion_strategy: str = "rrf",   # "rrf" | "weighted" | "simple"
    ) -> list[dict]: ...

class Reranker:
    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int = 10,
        criteria_weights: dict | None = None,
    ) -> list[dict]: ...
```

---

## 分阶段执行

### 阶段 0：环境与骨架 ✅

- [x] 创建 `src/`、`notebooks/`、`scripts/`、`tests/`、`outputs/samples/`
- [x] `requirements.txt` 增补：`rank-bm25`、`transformers`（复用）等
- [x] 明确数据路径（样本 / 全量）与默认 collection 名 → `src/config.py`

**阶段 0 完成说明**

- 本阶段先把「检索施工场地」搭好：目录、依赖、双库路径（样本 vs 全量）、slim 本地副本约定。
- 目标是不再在写 BM25/融合代码时被路径和环境问题卡住；`config.py` 成为后续所有模块找数据的统一入口。
- slim 复制到 `data/oa_comm_slim.jsonl` 后，重排的 recency/authority 不再依赖外接盘在线。

**阶段 0 实现说明（代码路径 / 函数 / 方法）**

- `src/config.py`
  - `resolve_chunks_path(mode)`：样本 → `03 .../chunks_sample.jsonl`；全量 → E: `oa_comm_chunks.jsonl`。
  - `resolve_chroma(mode)`：样本 `chroma_db`/`pmc_oa_comm_sample`；全量 `chroma_db_full`/`pmc_oa_comm_full`。
  - `resolve_slim_path()`：优先 `06 .../data/oa_comm_slim.jsonl`，缺失时回退 E: 权威源。
- `requirements.txt`：新增 **`rank-bm25`**（BM25 索引）。
- `notebooks/retrieval-pipeline.ipynb` **C0**：`MODE=sample` 与环境探测。

### 阶段 1：BM25 关键词检索 ✅

- [x] 从 03 chunks 读取 `chunk_id/text/doc_id/source_title/...`
- [x] 英文分词（小写、去停用词、保留数字医学术语）
- [x] 构建 BM25 索引并支持 `top_k`
- [x] 输出统一候选格式（含 `source`, `score`, `rank`, `chunk_id`）

**阶段 1 完成说明**

- 本阶段补上「关键词这一路」：向量检索擅长语义，BM25 擅长药名、年份、guideline 等字面匹配。
- 样本库 1,267 条上建索引约 0.1s，为后续「双路召回 + 融合」打基础。
- 输出候选 dict 格式与向量路对齐，方便 `fusion.py` 直接合并。

**阶段 1 实现说明（代码路径 / 函数 / 方法）**

- `src/bm25_index.py`
  - `tokenize(text)`：英文分词；保留 `2015`、`plasmodium` 等数字/医学 token。
  - `BM25Index.build_from_jsonl(path)`：从 chunks JSONL 建索引。
  - `BM25Index.search(query, top_k)`：返回带 `source=bm25`、`score`、`rank` 的候选列表。
- `tests/test_bm25.py`：样本库建索引与 top_k 检索。
- `outputs/samples/bm25_examples.json`：notebook 导出样例。

### 阶段 2：多路召回与融合 ✅

- [x] 向量召回：复用 04 `builder.query()`（输入 05 `vector_query`）
- [x] 关键词召回：BM25（输入 05 `keyword_query`）
- [x] 实现三种融合：
  - [x] `simple`：合并去重
  - [x] `rrf`：Reciprocal Rank Fusion
  - [x] `weighted`：向量分更高权重
- [x] 输出融合后候选（含分路得分与最终分）

**阶段 2 完成说明**

- 本阶段把 05 增强 query 真正接到 04 向量 + 本阶段 BM25 两路上，并回答「两路结果怎么合在一起」。
- C5/C7 实测：metformin 等 query **向量 Top-5 与 BM25 Top-5 可零重叠**，因此不能只用 simple 合并；**默认策略定为 `rrf`**。
- 融合后每条候选带 `vector_rank`/`bm25_rank`/`fusion_score`，便于 notebook 对比与后续重排。

**阶段 2 实现说明（代码路径 / 函数 / 方法）**

- `src/multipath_retriever.py`
  - `MultiPathRetriever.retrieve(query_info, ...)`：并行取向量路与 BM25 路，返回两路 hits。
  - `chroma_results_to_hits()`：04 Chroma 结果 → 统一候选 dict。
- `src/fusion.py`
  - `fuse_simple()` / `fuse_rrf()` / `fuse_weighted()` / `fuse(strategy=...)`：三种融合策略；pipeline 默认 **`rrf`**。
- `tests/test_fusion.py`：RRF 与 weighted 行为。
- `notebooks/retrieval-pipeline.ipynb` **C6–C7**：五 query 融合对比；`fusion_examples.json`。

### 阶段 3：重排序器 ✅

- [x] 接入 `BAAI/bge-reranker-base`（或同级可用模型）
- [x] query-doc 对打分（tokenize → 推理 → 概率/分数）
- [x] 多准则重排（可配置）：
  - [x] relevance（reranker score）
  - [x] recency（按 `pub_year` 线性衰减，来自 slim 回查）
  - [x] authority（期刊权重，规则表）
- [x] 产出 top_k 最终列表 + 解释字段

**阶段 3 完成说明**

- 本阶段在「召回一堆候选」之后做精排：cross-encoder 看 query–段落相关性，再叠加发表年份与期刊权威度。
- 年份/期刊不进 Chroma metadata，而是检索后按 `doc_id` **回查 slim**——与 04 不重建索引的决策一致。
- 样本库上 malaria after 2015 等 query 暴露时效验证不足（库内缺 2015+ 篇），但 recency 链路已通。

**阶段 3 实现说明（代码路径 / 函数 / 方法）**

- `src/reranker.py`
  - `Reranker.rerank(query, candidates, top_k, criteria_weights)`：BGE reranker 打分 + 多准则加权。
- `src/rerank_features.py`
  - `SlimMetadataLookup`：按 `doc_id` 读 `pub_year`/`journal`。
  - `recency_score()` / `authority_score()` / `extract_year_hint()` / `combine_criteria_scores()`。
- `tests/test_reranker.py`：relevance-only 与多准则组合。
- `notebooks/retrieval-pipeline.ipynb` **C8–C9**：重排演示；`rerank_examples.json`。

### 阶段 4：完整流水线联调 ✅

- [x] 串联：`enhancer -> multipath retrieve -> fusion -> rerank` → `src/pipeline.py`
- [x] notebook 演示 C10–C11（`RetrievalPipeline.run` + 导出 `pipeline_eval.json`）
- [x] CLI `run_retrieval_eval.py` 批量评估并导出 JSON（支持 `--skip-rerank` / `--check-only`）
- [x] 单元测试 `tests/test_pipeline.py`

**阶段 4 完成说明**

- 本阶段把前面四块拼成 **一条 `pipeline.run(query)`**：输入自然语言，输出带 `enhanced`/`retrieval`/`reranked` 的完整 dict。
- 样本库 5 条 query 端到端跑通；`pipeline_eval.json` 成为 08 离线检索适配器的标准输入。
- CLI 支持跳过重排加速调试；`--check-only` 做环境自检。

**阶段 4 实现说明（代码路径 / 函数 / 方法）**

- `src/pipeline.py`
  - `RetrievalPipeline.from_mode("sample"|"full")`：按模式挂载 Chroma/BM25/slim 路径。
  - `RetrievalPipeline.run(query)`：enhance → retrieve → fuse → rerank 一站式。
  - `build_eval_report()`：批量评测汇总 latency 分位数。
- `scripts/run_retrieval_eval.py`：CLI 批量评测；默认写出 `pipeline_eval.json`。
- `tests/test_pipeline.py`：mock 双路 + 端到端结构。
- `outputs/samples/pipeline_eval.json`：5 条 query 快照（08/09 上游）。

```bash
# 环境检查
python scripts/run_retrieval_eval.py --check-only

# 快速评测（跳过重排）
python scripts/run_retrieval_eval.py --skip-rerank --top-k-fused 5 --top-k-final 3

# 完整评测（含 reranker）
python scripts/run_retrieval_eval.py --output outputs/samples/pipeline_eval.json
```

### 阶段 5：测试与交付 ✅

- [x] 样例输出：`retrieval_compare.json`、`rerank_examples.json`、`pipeline_eval.json` 等 7 份
- [x] 单元测试：BM25 / fusion / reranker / pipeline（7 文件全部通过，2026-06-17）
- [x] 更新根目录 `README.md` 阶段 06 条目
- [x] 阶段报告：`docs/检索流水线报告.md`

**阶段 5 完成说明**

- 本阶段完成收口：单测全绿、正式报告、README 与 C12 可选全量联调结论写入 schedule。
- **样本库验证链路正确**；全量 C12 证明 metformin 等 query 在全量 Chroma 下质量显著优于样本，但 BM25 全量索引与 rerank 时延仍需生产优化。
- 后续 07 消费 `reranked`；LangChain_RAG 生产须 `from_mode("full")`（见 §验证范围说明）。

**阶段 5 实现说明（代码路径 / 函数 / 方法）**

- `tests/`：7 个测试文件覆盖 BM25、fusion、reranker、pipeline。
- `docs/检索流水线报告.md`：任务书对照、模块说明、样本/全量验证摘要。
- `outputs/samples/pipeline_eval_full.json`：C12 全量联调（可选）；3/3 query 样本 vs 全量 Top-1 均不同。
- 根目录 `README.md`：06 交付物速查 + **样本库 vs 全量**切换表。

---

## Notebook 样本库验证摘要（2026-06-15，`retrieval-pipeline.ipynb` C0–C8）

| 项 | 结果 |
|----|------|
| 环境 | 样本 chunks 1,267 条；Chroma `pmc_oa_comm_sample`；slim 本地副本可读 |
| BM25 建索引 | ~0.1 s；分词保留 `2015` / `plasmodium` 等数字医学 token |
| 双路诊断（C5） | `metformin cardiovascular effects`：向量 Top-5 与 BM25 Top-5 **零重叠** → 融合有必要 |
| RRF 融合（C6） | 5 条 schedule query 均返回融合候选；含 `vector_rank` / `bm25_rank` / `fusion_score` |
| 三策略对比（C7） | 同 query 下 `simple`≈纯向量序；`rrf`/`weighted` 引入 BM25 独有候选（如 `PMC521687`） |
| 默认策略 | **确认 `rrf`**（见下方「融合策略取舍」）；`weighted` 为备选 |

### 融合策略取舍（C7 实测，`metformin cardiovascular effects`）

| 策略 | Top-5 特征 | 结论 |
|------|-----------|------|
| **simple** | 与向量路 5/5 相同 | 双路零重叠时 **无法** 纳入 BM25 结果 → **不作默认** |
| **rrf** | 保留向量 #1，插入 BM25 独有 `PMC521687`、`PMC521493` | **作 pipeline 默认**；不依赖分数尺度 |
| **weighted** | Top-5 集合与 rrf **4/5 相同**，仅次序略异 | 保留为可调备选（`vector_weight=0.6`） |

**决策**：维持 `DEFAULT_FUSION_STRATEGY="rrf"`；三种策略均保留在代码与 C7 对比，非淘汰赛。

### C8 重排摘要（样本库）

| Query | 关注点 | 实测 |
|-------|--------|------|
| metformin… | 融合+重排 | RRF 纳入 BM25 候选；rerank 顶位为心血管相关但无 metformin 字面 |
| malaria after 2015 | recency | `year_hint=2015` 已生效，但样本库 Top 均为 2004 年文献，时效验证不足 |

### 验证 query 抽查（RRF 融合 Top-1）

| Query | RRF Top-1 | 简要结论 |
|-------|-----------|----------|
| `metformin cardiovascular effects` | `PMC523838_chunk2`（心血管 lipid） | 向量主导；RRF 第 2 位起纳入 BM25 候选 |
| `papers on malaria after 2015` | `PMC522803`（malaria 相关） | 融合命中；C8 recency 链路通但样本均为 2004 年 |
| `MI treatment guideline` | `PMC522817`（clinical practice guideline） | 关键词 guideline 生效；第 2 位 `PMC512285` 为 MI 结局 |
| `circadian rhythm sliding window chunks` | `PMC524494_chunk0` | strategy filter 下向量路偏短 chunk；第 2 位 `PMC517509` 含 circadian |
| `warfarin atrial fibrillation elderly` | （见 `fusion_examples.json`） | 双路医学术语召回正常 |

### 已知现象（样本库局限，不阻塞阶段 4）

1. 带 `strategy=sliding_window` 的 query 在 Chroma 样本库走 **post-filter 降级**（与 05 一致）。
2. 样本库仅 1,267 chunks，metformin 等 query 难命中药名字面；**全量库**联调后质量会提升。
3. `year_*` 在重排层通过 `year_hint` 降权旧文献，但样本库缺少 2015+ 疟疾篇，时效效果不明显。
4. C8 首次运行需下载 reranker（~1.1GB），后续 cached 约 1–3 分钟/5 query。

### C10–C11 端到端 pipeline 验证（`pipeline_eval.json`，2026-06-17）

| 项 | 结果 |
|----|------|
| 链路 | enhance → RRF 融合（top_k=10）→ rerank（top_k_final=5）一次 `pipeline.run()` 完成 |
| 时延 | p50 **86 ms**（模型已缓存）；p95 **3919 ms**（首条含 reranker 冷启动） |
| 5/5 query | 均返回非空 `reranked`；MI / warfarin / circadian 与 C6 预期一致 |

| Query | Pipeline Top-1 | 说明 |
|-------|----------------|------|
| metformin cardiovascular effects | `PMC520826` | 心血管 biomarker 文献（BM25 路）；与 C8 顶位不同因融合池更大 |
| papers on malaria after 2015 | `PMC523837` | 疟疾相关；样本库仍无 2015+ 篇 |
| MI treatment guideline | `PMC522817` | 指南类，与 C6/C8 一致 |
| circadian rhythm sliding window chunks | `PMC524494_chunk1` | sliding_window chunk |
| warfarin atrial fibrillation elderly | `PMC509245` | 房颤抗凝 RCT |

### C12 全量盘联调（`pipeline_eval_full.json`，2026-06-18）

| 项 | 结果 |
|----|------|
| 挂载 | `chroma_db_full`（6,107,296）+ E: `oa_comm_chunks.jsonl`；BM25 **探测** 前 100,000 条（31.5s），非 610 万全库 BM25 |
| 时延 | total p50 **34.1 s** / p95 **35.2 s**；`retrieve_ms` 140–1704 ms；**瓶颈在 rerank_ms≈33–34 s/条** |
| 样本 vs 全量 Top-1 | **3/3 不一致**（预期：样本库仅为 1,267 条子集） |

| Query | 样本 Top-1 | 全量 Top-1 | 全量解读 |
|-------|-----------|-----------|----------|
| metformin cardiovascular effects | `PMC520826` | **`PMC2566605_chunk2`** | ✅ 真正 metformin T1DM RCT；`relevance=0.93`，样本库无法命中 |
| MI treatment guideline | `PMC522817` | `PMC2637970` | 心梗修复（MI 主题）；非 guideline 字面，但比样本更贴 MI |
| papers on malaria after 2015 | `PMC523837` | `PMC12822982` | ⚠️ `pub_year=2026` 满足 recency，但内容为 cocaine 监测，**非疟疾**；recency 权重需与 relevance 联调 |

**结论**：全量 Chroma + 探测 BM25 + rerank 链路已打通；metformin 等 query 在全量下质量显著优于样本库。malaria 时效 query 暴露 recency 单独抬升非相关新文献的风险——RAG 生产建议增大 `top_k_fused`、全量 BM25 离线建索引、并监控 rerank 分项。

---

## 验证用例（首批）

| # | 输入查询 | 关注点 |
|---|----------|--------|
| 1 | `metformin cardiovascular effects` | 向量/关键词都应命中，融合排序稳定 |
| 2 | `papers on malaria after 2015` | 年份意图是否在 rerank 体现（recency） |
| 3 | `MI treatment guideline` | 缩写扩展后召回是否提升 |
| 4 | `circadian rhythm sliding window chunks` | strategy 过滤与召回兼容 |
| 5 | `warfarin atrial fibrillation elderly` | 医学术语 + 长尾关键词检索能力 |

---

## 评估指标（本周可落地）

| 维度 | 指标 | 说明 |
|------|------|------|
| 召回覆盖 | Recall@K（近似） | 对固定 query 检查是否包含预期文献 |
| 排序质量 | MRR / nDCG（小样本） | 用人工标注 20~30 条 query-doc 相关性 |
| 时延 | p50 / p95 latency | 分解：向量、BM25、融合、重排 |
| 稳定性 | 失败率 | where/filter 降级后是否稳定返回 |

---

## 交付产物清单（预填）

| 产物 | 格式 | 路径 | Git |
|------|------|------|-----|
| 多路检索模块 | Python | `src/multipath_retriever.py` | ✅ |
| BM25 索引模块 | Python | `src/bm25_index.py` | ✅ |
| 融合策略模块 | Python | `src/fusion.py` | ✅ |
| 重排序模块 | Python | `src/reranker.py` | ✅ |
| 端到端流水线 | Python | `src/pipeline.py` | ✅ |
| 演示 notebook | `.ipynb` | `notebooks/retrieval-pipeline.ipynb` | ✅ |
| 对比样例输出 | JSON | `outputs/samples/retrieval_compare.json` | ✅ |
| 融合样例输出 | JSON | `outputs/samples/fusion_examples.json` | ✅ |
| BM25 样例输出 | JSON | `outputs/samples/bm25_examples.json` | ✅ |
| 向量 smoke 输出 | JSON | `outputs/samples/vector_smoke_sample.json` | ✅ |
| 重排样例输出 | JSON | `outputs/samples/rerank_examples.json` | ✅（C9 导出） |
| Pipeline 评测输出 | JSON | `outputs/samples/pipeline_eval.json` | ✅（C11 / CLI） |
| 全量联调输出 | JSON | `outputs/samples/pipeline_eval_full.json` | ✅（C12，可选） |
| 阶段报告 | Markdown | `docs/检索流水线报告.md` | ✅ |
| 向量库 | ChromaDB | 04 阶段已有 | ❌ |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| reranker 模型推理慢 | 总时延上升 | 先小 top_n 重排（如 30→10） |
| 年份/期刊缺失或不规范 | recency/authority 不稳定 | 缺失时回退 relevance-only |
| BM25 语料过大内存压力 | 开发效率下降 | 先样本库验证，再分片/缓存 |
| Chroma where 不稳定 | 召回异常 | 复用 04 的 post-filter 降级策略 |

---

## 本周执行顺序（建议）

1. 先完成 BM25 + 向量双路召回与融合（不含重排），拿到可运行 baseline  
2. 再接入 reranker relevance-only，确认质量提升  
3. 最后追加 recency/authority 多准则特征与评测导出  

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-06-15 | 创建阶段 06 `schedule.md`，对齐任务书与 04/05 实际接口，待启动实施 |
| 2026-06-15 | **阶段 0 完成**：目录骨架、`requirements.txt`、`src/config.py` 路径与双库配置 |
| 2026-06-15 | **slim 本地化**：`E:\...\oa_comm_slim.jsonl` → `data/oa_comm_slim.jsonl`；`resolve_slim_path()` 优先本地 |
| 2026-06-15 | **阶段 1 完成**：`src/bm25_index.py` + `tests/test_bm25.py`（样本库 1,267 条验证通过） |
| 2026-06-15 | **阶段 2 完成**：`multipath_retriever.py` + `fusion.py`；notebook C6–C7 融合对比 |
| 2026-06-15 | **notebook C0–C8 样本验证通过**；导出 `fusion_examples.json` 等 4 份样例 |
| 2026-06-17 | **阶段 3 完成**：`reranker.py` + `rerank_features.py`；notebook C8–C9 |
| 2026-06-18 | **阶段 4 完成**：`pipeline.py` + CLI 评测 + notebook C10–C11；导出 `pipeline_eval.json` |
| 2026-06-18 | **阶段 5 完成**：全测试通过 + 阶段报告 `docs/检索流水线报告.md` |
| 2026-06-18 | **C12 全量联调**：`pipeline_eval_full.json`；3 query 样本 vs 全量 Top-1 全不同；metformin 全量命中真实 RCT |

