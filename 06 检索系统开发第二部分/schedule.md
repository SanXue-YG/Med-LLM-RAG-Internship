# 06 检索系统开发第二部分 — 执行计划

> **状态：🔄 进行中（阶段 0 已完成）**
>
> **本阶段范围（任务书）**：实现多路检索（向量 + BM25）→ 融合 → 重排序，并与 05 查询增强模块打通为完整检索流水线。
>
> **上游依赖**：
> - 05：`MedicalQueryEnhancer` / `EnhancedQuery`
> - 04：`DocumentEmbedder` / `ChromaIndexBuilder` + Chroma 库
> - 03：`oa_comm_chunks.jsonl`（BM25 语料来源，title+abstract chunk）
> - 02：`oa_comm_slim.jsonl`（重排 recency/authority 回查，`doc_id` → `pub_year` / `journal`）

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
| 语料来源 | BM25 首版用 `03 .../chunks_sample.jsonl` 验证，再切全量 | 降低首轮开发风险 |
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
│   └── retrieval-pipeline.ipynb     # C0-C6 演示与验证
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

### 阶段 1：BM25 关键词检索 ☐

- [ ] 从 03 chunks 读取 `chunk_id/text/doc_id/source_title/...`
- [ ] 英文分词（小写、去停用词、保留数字医学术语）
- [ ] 构建 BM25 索引并支持 `top_k`
- [ ] 输出统一候选格式（含 `source`, `score`, `rank`, `chunk_id`）

### 阶段 2：多路召回与融合 ☐

- [ ] 向量召回：复用 04 `builder.query()`（输入 05 `vector_query`）
- [ ] 关键词召回：BM25（输入 05 `keyword_query`）
- [ ] 实现三种融合：
  - [ ] `simple`：合并去重
  - [ ] `rrf`：Reciprocal Rank Fusion
  - [ ] `weighted`：向量分更高权重
- [ ] 输出融合后候选（含分路得分与最终分）

### 阶段 3：重排序器 ☐

- [ ] 接入 `BAAI/bge-reranker-base`（或同级可用模型）
- [ ] query-doc 对打分（tokenize → 推理 → 概率/分数）
- [ ] 多准则重排（可配置）：
  - [ ] relevance（reranker score）
  - [ ] recency（按 `pub_year` 线性衰减，来自 02 slim 回查）
  - [ ] authority（期刊权重，先做规则表）
- [ ] 产出 top_k 最终列表 + 解释字段

### 阶段 4：完整流水线联调 ☐

- [ ] 串联：`enhancer -> multipath retrieve -> fusion -> rerank`
- [ ] notebook 演示 C0-C6（至少 4 条英文医学 query）
- [ ] CLI `run_retrieval_eval.py` 批量评估并导出 JSON

### 阶段 5：测试与交付 ☐

- [ ] 单元测试：BM25 / fusion / reranker / pipeline
- [ ] 样例输出：`retrieval_compare.json`、`rerank_examples.json`
- [ ] 更新根目录 `README.md` 阶段 06 条目
- [ ] 补充阶段报告（是否单独 docs，按老师口径）

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
| 重排样例输出 | JSON | `outputs/samples/rerank_examples.json` | ✅ |
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

