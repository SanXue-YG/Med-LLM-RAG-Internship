# 04 向量化与索引构建 — 执行计划

> **状态：📋 决策已定，待搭建**（2026-06-01）
>
> **本阶段策略：先抽样验证**（复用阶段 3 的 1,267 chunks），跑通"嵌入 → 建库 → 检索"全流程后，再视情况扩展到全量。

---

## 已确认决策（2026-06-01）

| 决策项 | 结论 |
|--------|------|
| **嵌入模型** | `BAAI/bge-small-en-v1.5`（384 维） |
| **运行环境** | Windows + GPU（notebook 入口检测并记录设备信息，便于日后对齐） |
| **数据范围** | **先抽样验证**：直接复用阶段 3 的 `chunks_sample.jsonl`（1,267 chunks），复制到本阶段 `data/processed/` |
| **后续全量** | 抽样流程跑通后再扩展到 610 万全量 |

---

## 与第三阶段的衔接关系

### 第三阶段已产出（直接复用）

| 产出物 | 路径 | 用途 |
|--------|------|------|
| 验证样本 chunks | `03 文档解析与分割/data/processed/chunks_sample.jsonl` | **本阶段输入**（1,267 chunks，复制到 04 复用） |
| 全量 chunks | `E:\med-llm-rag-datasets\processed\oa_comm_chunks.jsonl` | 后续全量扩展时使用（6,107,296 chunks） |
| chunk 字段结构 | — | `chunk_id, text, doc_id, chunk_index, total_chunks, source_title, token_count, strategy` |

> 样本数据复用说明详见 `笔记/04笔记`：阶段 3 样本为"前 1,000 篇完整文献"（非随机），多块文献分块完整、无残缺，可直接用于本阶段流程验证。

### 数据流（本阶段：抽样验证）

```
阶段 3 chunks_sample.jsonl (1,267 chunks)
    ↓ 复制到 04 data/processed/
    ↓ 加载 bge-small-en-v1.5（384 维，GPU）
    ↓ 批量生成文档向量（文档端不加指令）
    ↓ 写入 ChromaDB（余弦相似度 hnsw:space=cosine）
向量索引（持久化） + 元数据
    ↓ 测试查询（查询端加 BGE 指令）
返回相关医学文献片段 + 元数据过滤验证

  ——（流程跑通后，可换全量 oa_comm_chunks.jsonl 扩展）——
```

---

## 嵌入模型选择

### 任务书候选

| 模型 | 维度 | 显存 | 说明 |
|------|------|------|------|
| `BAAI/bge-small-en-v1.5` | **384** | 轻量 | 推荐：与 01 阶段同维度，效果优于 all-MiniLM |
| `BAAI/bge-base-en-v1.5` | 768 | ~8GB | 效果更好，资源占用翻倍 |
| `BAAI/bge-large-en-v1.5` | 1024 | ~16GB | 最佳效果，资源要求高 |
| OpenAI `text-embedding-3-*` | 1536+ | 付费 API | 需联网与费用 |

### ✅ 已选定：`bge-small-en-v1.5`（384 维）

原因：

1. **规模适配**：610 万 chunks，384 维向量约占 9.4 GB（float32），base/large 翻倍或更多
2. **本机资源**：当前为 Windows + GPU 环境，small 模型轻量、GPU 上嵌入更快；即便回退 CPU 也可运行
3. **效果保证**：BGE-small 在 MTEB 英文检索榜上优于 all-MiniLM-L6-v2
4. **查询指令**：BGE 检索时查询端需添加指令前缀
   `"Represent this sentence for searching relevant passages: {query}"`

> **注意**：token 长度统计（02/03 阶段）基于 all-MiniLM-L6-v2 tokenizer；BGE 的 tokenizer 不同，但 `chunk_size=400` 仍在 BGE 的 512 上限内，无需重新分割。

---

## 执行步骤

### 阶段 0：环境与配置

- [ ] 创建目录结构：`data/processed/`、`src/`、`notebooks/`、`outputs/`
- [ ] **复制阶段 3 样本数据**：
  `03 .../data/processed/chunks_sample.jsonl` → `04 .../data/processed/chunks_sample.jsonl`
- [ ] 复用 `med-rag-verify` 环境，确认/安装依赖：
  - `chromadb`（向量库）
  - `sentence-transformers` 或 `FlagEmbedding`（BGE 模型）
- [ ] **notebook 入口检测并记录运行环境**（作为背景信息，便于日后对齐）：
  - GPU 是否可用（`torch.cuda.is_available()`）、设备名、显存
  - PyTorch / CUDA 版本、嵌入实际使用的 device（cuda / cpu）
- [ ] 定义路径常量与向量库持久化目录
  - 向量库输出：`E:\med-llm-rag-datasets\chroma_db\`（体积大，放外接盘）
- [ ] 首次下载 BGE 模型权重（联网）

### 阶段 1：嵌入模型选择与加载（任务§1）

- [ ] 初始化嵌入模型 `bge-small-en-v1.5`（384 维），自动选 GPU（可用时）
- [ ] 封装 `encode_documents(texts)`：文档端，**不加**指令前缀（建库用）
- [ ] 封装 `encode_queries(texts)`：查询端，**自动加** BGE 指令前缀（检索用）
- [ ] 在验证样本（1,267 chunks）上测试模型加载与编码、确认输出维度 = 384

### 阶段 2：向量数据库配置与索引构建（任务§2）

- [ ] 创建 ChromaDB 持久化 collection（**余弦相似度** `hnsw:space=cosine`）
- [ ] 构建元数据：`doc_id, chunk_index, total_chunks, source_title, token_count, strategy`
- [ ] 生成唯一 id：`doc_id + "_" + chunk_index`（任务书要求；与 chunk_id 一致）
- [ ] **分批入库 + 断点续传**（复用 02/03 阶段模式，应对 610 万规模）
  - 按批次（如 5,000 chunks/批）编码并 `add`
  - 进度保存到 `progress.json`，支持中断续传
- [ ] 验证索引大小（`collection.count()` 与输入一致）
- [ ] 保存统计信息 `index_stats.json`：

```python
stats = {
    "collection_name": "...",
    "total_chunks": ...,
    "embedding_model": "BAAI/bge-small-en-v1.5",
    "embedding_dimension": 384,
    "index_built_at": "...",
    "chunk_size_stats": {"mean": ..., "max": ..., "min": ...},
    "metadata_fields": [...],
}
```

- [ ] 实现 `query()` 查询接口：
  - 参数：`query_text`、`n_results`、`where_filter`（元数据过滤）
  - 返回：相关文档片段 + 元数据 + 距离

### 阶段 3：质量验证（任务§3）

- [ ] **基础统计验证**：向量数量与输入一致、样本元数据完整
- [ ] **相似性检索验证**：从索引中取文本作查询，测试自相似性（应命中自身）
- [ ] **边界情况验证**：空查询、超长查询的健壮性
- [ ] **元数据过滤验证**：按 `pub_year` / `strategy` 等过滤检索正常工作
- [ ] 导出验证报告 `query_validation.json`

---

## 目录结构规划

```
04 向量化与索引构建/
├── 任务.txt
├── schedule.md                  # 本文件
├── requirements.txt             # 依赖说明（复用 02 环境 + chromadb）
├── data/
│   └── processed/
│       └── chunks_sample.jsonl  # 复制自阶段 3（1,267 chunks，本阶段输入）
├── docs/
│   └── 向量化与索引报告.md       # 正式交付报告（完成后）
├── src/
│   ├── __init__.py
│   ├── embedder.py              # 嵌入模型封装（BGE，含 encode_documents/encode_queries）
│   └── index_builder.py         # ChromaDB 索引构建 + 查询
├── notebooks/
│   ├── vectorize-index.ipynb    # 验证样本（小规模，先做）
│   └── vectorize-index-full.ipynb  # 全量索引构建（后续扩展）
└── outputs/
    ├── tables/                  # 全量索引统计
    │   ├── index_stats.json
    │   └── query_validation.json
    └── samples/                 # 验证样本统计
        ├── index_stats_sample.json
        └── query_validation_sample.json
```

---

## 交付产物清单（任务§本周产出）

| 产物 | 格式 | 路径 | Git |
|------|------|------|-----|
| 向量数据库文件 | ChromaDB | `E:\med-llm-rag-datasets\chroma_db\` | ❌ 外接硬盘 |
| 索引统计 | JSON | `outputs/tables/index_stats.json` | ✅ |
| 查询验证结果 | JSON | `outputs/tables/query_validation.json` | ✅ |
| 验证样本索引统计 | JSON | `outputs/samples/index_stats_sample.json` | ✅ |
| 正式报告 | Markdown | `docs/向量化与索引报告.md` | ✅ |

---

## 预估资源与工作量

| 项目 | 预估 |
|------|------|
| 向量存储（bge-small 384维） | ~9.4 GB（向量）+ ChromaDB 索引/元数据，合计约 15-20 GB |
| 嵌入计算（610 万 chunks） | CPU 上较慢，建议有 GPU；分批 + 断点续传 |
| 环境准备 | 0.5h |
| 代码实现 | 2-3h |
| 验证样本跑通 | 0.5h |
| 全量索引构建 | 数小时（取决于 GPU/CPU 与磁盘 IO） |
| 验证与报告 | 1h |

---

## 风险与应对（参考任务书提示）

1. **内存/显存不足**：减小 `batch_size`；使用 `bge-small`；分批处理
2. **嵌入速度慢**：优先使用 GPU；必要时考虑量化嵌入模型
3. **运行中断**：断点续传机制（沿用 02/03 阶段 `progress.json` 模式）
4. **磁盘空间**：向量库放外接盘 `E:\`，避免占满系统盘
5. **检索结果不相关**：检查 chunk 质量；BGE 查询端务必加指令前缀；必要时尝试 base 模型

---

## ⚠️ 实现注意事项（供未来 RAG 开发回顾）

> 这些是建库时已知、但**主要在后续"对接 LLM 构建 RAG"阶段才会踩坑**的点，提前记录。

### 1. BGE 查询指令：建库 vs 查询不对称

- **建库阶段（本阶段 04）**：文档 chunk **直接嵌入，不加任何指令前缀**，与 all-MiniLM 用法一致，无需特殊处理。
- **查询阶段（后续 LangChain RAG）**：用户问题在嵌入前**需要加指令前缀**：
  `Represent this sentence for searching relevant passages: {query}`

### 2. "自动加"取决于嵌入模型的调用库，与 LLM 无关

- 指令是**嵌入模型（embedding）**侧的事，**不是 LLM（deepseek-r1 等）**侧的事，不要混淆。
- 是否需要手动加，取决于查询时用哪个嵌入 API：

  | 调用方式 | 是否自动加指令 |
  |----------|--------------|
  | `sentence-transformers` `encode()` | ❌ 需手动加 |
  | `FlagEmbedding` `encode_queries()` | ✅ 自动 |
  | LangChain `HuggingFaceBgeEmbeddings.embed_query()` | ✅ 自动（需配置 `query_instruction`） |

- **漏加不会报错，但检索准确率静默下降**，务必确认所用 API 的行为。

### 3. 建库与查询必须用同一嵌入模型

- 两端使用的 BGE 模型（及版本/维数）必须完全一致，否则向量空间不对齐，检索失效。
- 本阶段建库用的模型，需在 `index_stats.json` 中明确记录，供后续 RAG 阶段对齐。

### 4. 代码封装建议

- 在 `src/embedder.py` 中封装两个明确方法：
  - `encode_documents(texts)` —— 不加指令（建库用）
  - `encode_queries(texts)` —— 自动加指令（查询用）
- 从源头避免"查询端漏加指令"的静默劣化。

---

## 待确认事项

> 三项核心决策均已确定（见文首「已确认决策」），无待确认项。后续若抽样验证通过，再确认是否扩展到全量。

| 原待确认项 | 结论 |
|-----------|------|
| 嵌入模型 | ✅ `bge-small-en-v1.5`（384 维） |
| 是否使用 GPU | ✅ Windows + GPU，入口检测并记录设备信息 |
| 全量 vs 抽样 | ✅ 先抽样（复用阶段 3 的 1,267 chunks） |

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-06-01 | 阅读任务书，制定第四阶段执行计划 |
| 2026-06-01 | 确定三项决策：bge-small-en-v1.5 + GPU 环境 + 先抽样验证（复用阶段 3 样本） |
