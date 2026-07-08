# 04 向量化与索引构建 — 执行计划

> **状态：✅ 全量建库 + C3–C5 验证 + E: 备份已完成**（2026-06-02）
>
> **本阶段策略**：抽样验证（1,267 chunks）已跑通；**全量 6,107,296 chunks** 已在 D: `data/chroma_db_full/` 建库并完成质量验证。E: 权威备份已手动完成；**RAG 阶段挂载 D: 上暂留的 `chroma_db_full/`**（见文末「阶段收尾」与根目录 `README.md`）。
>
> **GitHub**：代码、notebook、验证 JSON 可上传；向量库目录已在 `.gitignore` 中排除，克隆后需本地保留或从 E: 恢复。

---

## 已确认决策（2026-06-01）

| 决策项 | 结论 |
|--------|------|
| **嵌入模型** | `BAAI/bge-small-en-v1.5`（384 维） |
| **运行环境** | Windows + GPU（notebook 入口检测并记录设备信息，便于日后对齐） |
| **数据范围** | **先抽样验证**：直接复用阶段 3 的 `chunks_sample.jsonl`（1,267 chunks），复制到本阶段 `data/processed/` |
| **后续全量** | ✅ 已完成（6,107,296 chunks → `data/chroma_db_full/`） |
| **RAG 挂载** | ✅ D: `data/chroma_db_full/`（E: 为备份；见「阶段收尾 §5」） |

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

### 阶段 0：环境与配置 ✅ 已完成（2026-06-01）

- [x] 创建目录结构：`data/processed/`、`src/`、`notebooks/`、`outputs/`、`docs/`
- [x] **复制阶段 3 样本数据**：`chunks_sample.jsonl`（1,267 chunks）已复制到 `04 .../data/processed/`
- [x] 复用 `med-rag-verify` 环境，依赖确认：
  - `chromadb` 1.5.9 ✅
  - `sentence-transformers` 5.5.1 ✅
- [x] **环境检测**（已写入 notebook C0 单元格）
- [x] 定义路径常量与向量库持久化目录
  - **验证期**：`04 .../data/chroma_db/`（工程内；**需重跑 notebook 重建** `pmc_oa_comm_sample`，当前目录可能已被全量半成品占用）
  - **全量期（当前）**：`04 .../data/chroma_db_full/`（D:）；归档见文末 **「阶段收尾」**
- [ ] 首次下载 BGE 模型权重（首次运行 notebook C1 时自动联网下载，约 130MB）

**已创建文件：**

| 文件 | 说明 |
|------|------|
| `src/embedder.py` | BGE 封装（`encode_documents` 不加指令 / `encode_queries` 加指令） |
| `src/index_builder.py` | ChromaDB 构建（余弦）+ 分批入库 + 断点续传 + 查询 |
| `src/__init__.py` | 模块导出 |
| `notebooks/vectorize-index.ipynb` | 抽样验证入口（C0~C5，向量库在工程内） |
| `notebooks/vectorize-index-full.ipynb` | 全量入口（向量库在外接盘） |
| `requirements.txt` | 依赖说明（含 GPU 安装指引） |
| `data/processed/chunks_sample.jsonl` | 复用阶段 3 样本（1,267 chunks） |

> ⚠️ **环境检测结果（重要）**：当前 PyTorch 为 **CPU 版**（`torch 2.11.0+cpu`，`cuda_available=False`），
> 暂时**用不了 GPU**。抽样验证（1,267 chunks）用 CPU 即可；**全量前需安装 CUDA 版 PyTorch**：
> `pip uninstall torch -y && pip install torch --index-url https://download.pytorch.org/whl/cu121`

**阶段 0 完成说明**

- 本阶段搭好向量化工程骨架：BGE embedder、Chroma index builder、样本/全量双 notebook 入口。
- 核心决策落地：**建库不加指令、查询加指令**（见 §实现注意事项）；样本先跑通再全量 610 万。
- 检测到默认 CPU 版 torch，全量前须 `setup_stage04_gpu.ps1`。

**阶段 0 实现说明（代码路径 / 函数 / 方法）**

- `src/embedder.py`：`DocumentEmbedder` 骨架（阶段 1 充实 `encode_documents`/`encode_queries`）。
- `src/index_builder.py`：`ChromaIndexBuilder` 骨架；余弦 `hnsw:space=cosine`。
- `notebooks/vectorize-index.ipynb` **C0**：环境检测与路径常量。

### 阶段 1：嵌入模型选择与加载（任务§1）

- [x] 初始化嵌入模型 `bge-small-en-v1.5`（384 维），自动选 device（cuda 可用时）
- [x] 封装 `encode_documents(texts)`：文档端，**不加**指令前缀（建库用）
- [x] 封装 `encode_queries(texts)`：查询端，**自动加** BGE 指令前缀（检索用）
- [x] 在验证样本上运行 notebook，确认模型加载与输出维度 = 384
- [x] 全量 notebook C1 通过（`transformers` 直载，见问题排查 §2）

**阶段 1 完成说明**

- 本阶段把 BGE 嵌入「用对」：建库与查询不对称是 BGE 官方要求，漏加查询指令会**静默降检索质量**。
- 改用 `transformers` 直载，规避 Windows Jupyter 下 `sentence_transformers` 内核崩溃。

**阶段 1 实现说明（代码路径 / 函数 / 方法）**

- `src/embedder.py`
  - `DocumentEmbedder.encode_documents(texts)`：chunk 文本直接嵌入（建库）。
  - `DocumentEmbedder.encode_queries(texts)`：自动前缀 `Represent this sentence for searching relevant passages:`。
- `notebooks/vectorize-index.ipynb` **C1**：384 维 smoke；`vectorize-index-full.ipynb` **C1** 全量复用。

### 阶段 2：向量数据库配置与索引构建（任务§2）

- [x] 创建 ChromaDB 持久化 collection（**余弦相似度** `hnsw:space=cosine`）
- [x] 构建元数据：`doc_id, chunk_index, total_chunks, source_title, token_count, strategy`
- [x] 生成唯一 id：`doc_id + "_" + chunk_index`（任务书要求；与 chunk_id 一致）
- [x] **分批入库 + 断点续传**（复用 02/03 阶段模式，应对 610 万规模）
  - 按批次（如 5,000 chunks/批）编码并 `add`
  - 进度保存到 `progress.json`，支持中断续传
- [x] 验证索引大小（全量用 `count_embeddings_sqlite()`，见 §9）
- [x] 保存统计信息 `index_stats.json`：

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

- [x] 实现 `query()` 查询接口：
  - 参数：`query_text`、`n_results`、`where_filter`（元数据过滤）
  - 返回：相关文档片段 + 元数据 + 距离
  - 全量 metadata 过滤见 §11 post-filter 降级

**阶段 2 完成说明**

- 本阶段把 610 万（或样本 1,267）chunk **写入 Chroma 持久化库**，支持中断续跑。
- 全量产物 `chroma_db_full`（~71 GB）是后续 RAG 语义检索底座；**勿与** `chroma_db` 半成品目录混淆（见「阶段收尾」）。
- `index_stats.json` 记录模型名与维度，供 05/06 对齐。

**阶段 2 实现说明（代码路径 / 函数 / 方法）**

- `src/index_builder.py`
  - `ChromaIndexBuilder.add_chunks_batch(...)`：分批 embed + 入库。
  - `ChromaIndexBuilder.query(...)`：内部调 `encode_queries`；支持 `where_filter`（大规模 post-filter 降级）。
  - `count_embeddings_sqlite()` / `repair_chroma_hnsw()`：全量条数校验与 HNSW 修复。
- `outputs/tables/index_stats.json`：全量 6,107,296 条统计。
- `notebooks/vectorize-index-full.ipynb` **C2/C2.5**：全量建库与 D: 迁移续跑。

### 阶段 3：质量验证（任务§3）

- [x] **基础统计验证**：向量数量与输入一致、样本元数据完整（全量 **6,107,296** → `index_stats.json`）
- [x] **相似性检索验证**：自相似 + 语义检索（C4）
- [x] **边界情况验证**：空查询、超长查询（C5）
- [x] **元数据过滤验证**：`strategy=sliding_window`（C5，见 §11 post-filter 降级）
- [x] 导出验证报告 `outputs/tables/query_validation.json`

**阶段 3 完成说明**

- 本阶段证明「库建对了、查得到」：条数一致、语义 query 命中相关文献、边界 query 不崩溃。
- 全量库 metadata 过滤可能走 post-filter 降级——与 05/06 行为一致，已在验证报告记录。

**阶段 3 实现说明（代码路径 / 函数 / 方法）**

- `outputs/tables/query_validation.json`：C3–C5 验证结果汇总。
- `outputs/samples/query_validation_sample.json`：样本库验证报告。
- `docs/向量化与索引报告.md`：正式交付；§实现注意事项供后续 RAG 回顾。

---

## 目录结构规划

```
04 向量化与索引构建/
├── 任务.txt
├── schedule.md                  # 本文件
├── requirements.txt             # 依赖说明（复用 02 环境 + chromadb）
├── data/
│   ├── processed/
│   │   ├── chunks_sample.jsonl  # 复制自阶段 3
│   │   └── oa_comm_chunks.jsonl # 全量输入（可选本地保留，~9 GB）
│   ├── chroma_db/               # 验证期 / 可重建（.gitignore）
│   └── chroma_db_full/          # 全量正式库（RAG 用，~71 GB，.gitignore）
├── docs/
│   └── 向量化与索引报告.md       # 正式交付报告（完成后）
├── src/
│   ├── __init__.py
│   ├── embedder.py              # 嵌入模型封装（BGE；transformers 直载，encode_documents/encode_queries）
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
| 向量数据库（验证） | ChromaDB | `04 .../data/chroma_db/` | ❌ 工程内（.gitignore，可重建） |
| 向量数据库（全量） | ChromaDB | `04 .../data/chroma_db_full/`（工程内 D:；可拷回 E: 存档） | ❌ `.gitignore` |
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
- **实现**：使用 `transformers.AutoModel` + mean pooling（不经 `sentence_transformers`），避免 Windows Jupyter 内核崩溃（见「问题排查记录 §2」）。

---

## 待确认事项

> 本阶段核心决策与全量扩展均已落地，无待确认项。

| 原待确认项 | 结论 |
|-----------|------|
| 嵌入模型 | ✅ `bge-small-en-v1.5`（384 维） |
| 是否使用 GPU | ✅ Windows + GPU（`torch 2.6.0+cu124`，RTX 4080） |
| 全量 vs 抽样 | ✅ 抽样已验证 → **全量 6,107,296 条已完成** |
| RAG 向量库位置 | ✅ 日常开发用 D: `data/chroma_db_full/`；E: 为权威备份 |

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-06-01 | 阅读任务书，制定第四阶段执行计划 |
| 2026-06-01 | 确定三项决策：bge-small-en-v1.5 + GPU 环境 + 先抽样验证（复用阶段 3 样本） |
| 2026-06-01 | 阶段 0 完成：搭建目录/代码框架/入口 notebook；环境检测发现 torch 为 CPU 版（全量前需装 CUDA 版） |
| 2026-06-01 | 抽样验证完成（1,267 chunks）：BGE + ChromaDB 建库与检索通过 |
| 2026-06-02 | GPU 环境就绪：`torch 2.6.0+cu124`（RTX 4080）；新增 `setup_stage04_gpu.ps1` |
| 2026-06-02 | **全量 C1 内核崩溃已修复**：`embedder.py` 改为 `transformers` 直载（见下方「问题排查」）；C1 通过 |
| 2026-06-02 | 修复 `vectorize-index-full.ipynb` C2 参数 cell 字面量 `\n` 导致的 SyntaxError |
| 2026-06-02 | 新增 **C2.5**：E: → 工程内 D: 迁移续跑；笔记 Q13 记录 Chroma 占盘结构 |
| 2026-06-02 | C2.5 全量跑通中：HNSW 修复 + D: `chroma_db_full`；Q14 记录 E: 占用误判与续跑机制 |
| 2026-06-02 | **全量建库完成**：6,107,296 条；`progress.json` 与 sqlite 一致 |
| 2026-06-02 | **C3–C5 验证通过**：`index_stats.json` + `query_validation.json` 已导出；见 §9–§11 与笔记 **Q17** |
| 2026-06-02 | 阶段收尾说明：D:→E: 归档与 `chroma_db` / `chroma_repair_test` 清理 → 见 **「阶段收尾」** |
| 2026-06-02 | **E: 备份已完成**（手动）；RAG 阶段采用 D: 暂留 `chroma_db_full/`；计划表与根目录 README 已更新供 GitHub 上传 |
| 2026-06-03 | **正式报告**：`docs/向量化与索引报告.md`（嵌入模型 `BAAI/bge-small-en-v1.5` 已标注） |

### 全量验证通过后的代码 / notebook 修改（回顾用）

| 修改 | 文件 | 目的 |
|------|------|------|
| `count_embeddings_sqlite()` | `index_builder.py` | 610 万库避免 `collection.count()` native 崩溃 |
| `get_stats(total_chunks=...)` | `index_builder.py` | C3 写统计时不重复 count |
| `repair_chroma_hnsw` 清理 stale `index_metadata.pickle` | `index_builder.py` | 修复「仅 pickle、无 bin」导致的 hnsw 加载失败 |
| `query()` post-filter 降级 | `index_builder.py` | C5 `where=` 报 `Error finding id` 时 over-fetch + Python 过滤 |
| C3 去掉 `pandas`，用 progress/sqlite 条数 | `vectorize-index-full.ipynb` | 避免 Jupyter 内核崩溃 |
| C2.5a `REPAIR_HNSW=False`（建库完成后）+ count 自动重试 | notebook | 勿误删完好 HNSW；hnsw 错时自动清理 pickle |
| builder 初始化用 sqlite 计数 | notebook | 重启后只 attach 库，不重跑 C2.5b |
| 改 `index_builder.py` 后 `importlib.reload` | 操作说明 | 方式 B：不重开 Kernel 加载新 query 逻辑 |

### 全量完成后推荐执行顺序（验证 / 重启后）

```
C0 → C1 → C2.5a（COPY_FROM_E=False, REPAIR_HNSW=False）
  → builder 初始化 cell（勿跑 C2.5b 全量建库）
  → C3 → C4 → C5
```

> C2.5a 之后**勿再跑 C0**（会把路径改回 E:）。修改 `index_builder.py` 后需 **Kernel Restart** 或对 `index_builder` 做 `importlib.reload` 再重建 `builder`（已集成入builder 初始化 cell）
---

## 问题排查记录

### 1. 全量前：PyTorch 为 CPU 版（Q11，见笔记）

| 现象 | `cuda_available=False`，`torch x.y.z+cpu` |
| 原因 | 01 `requirements.txt` 只锁 `torch==2.11.0`；Windows 默认 pip 装 CPU wheel |
| 处理 | 运行 `setup_stage04_gpu.ps1` 或手动从 PyTorch 官方 index 安装 CUDA 版 |

### 2. 全量 C1：Jupyter 内核崩溃（`The Kernel crashed`）

| 现象 | C1 打印 `device_info` 后，访问 `embedder.dimension` 加载模型时内核直接退出，无 Python traceback |
| 分析 | ① CLI 中同代码可跑通 → 非 CUDA/模型本身问题；② faulthandler 显示崩溃点在 `import sentence_transformers` 的依赖链（`pyarrow` / `datasets` / `sklearn`）；③ Windows + VS Code/Cursor Jupyter 对该 native 导入链更敏感；④ 仅 `pip install --force-reinstall pyarrow` 对本机仍可能复发 |
| 处理（最终方案） | **`src/embedder.py` 不再使用 `sentence_transformers`**，改为 `transformers.AutoModel` + mean pooling + L2 归一化；API 不变（`encode_documents` / `encode_queries`） |
| 操作 | Kernel → Restart → 从 C0 重跑；C1 `batch_size` 建议 128（12GB 显存笔记本） |
| 备注 | 02 环境仍可能装有 `sentence-transformers`，但 04 建库不再经其加载模型 |

### 3. 全量 C2：SyntaxError（字面量 `\n`）

| 现象 | `BATCH_SIZE = 512\nRESUME = True\n...` → `unexpected character after line continuation character` |
| 原因 | notebook 生成时误将换行写成 JSON 字符串内的 `\n` 字面量，整段变成一行非法 Python |
| 处理 | 改为三行独立赋值；并修正 C3 / 文末 markdown cell 中同类问题 |

### 4. 外接盘 I/O 瓶颈 → C2.5 工程内加速

| 现象 | ~4h 仅 ~15.7 万条；任务管理器磁盘 100%、GPU ~30% |
| 原因 | 全量 JSONL + `chroma_db` 均在 E:（My Passport USB HDD） |
| 处理 | notebook **【C2.5】**：复制到 `data/processed/` + `data/chroma_db_full/`，覆盖 `INPUT_JSONL` / `PERSIST_DIR`，`RESUME=True` 续跑 |
| 操作 | 跑通 C0→C1 后**跳过 C2**，直接 C2.5；首次 `COPY_FROM_E=True`，复制完改 `False` |
| 存档 | 全量完成后将 `data/chroma_db_full/` 拷回 `E:\med-llm-rag-datasets\chroma_db\` |
| 笔记 | Chroma 目录结构与占盘见 `笔记/04笔记.md` **Q13**；E: 占用与续跑见 **Q14** |

### 5. C2.5：`Error loading hnsw index`

| 项 | 说明 |
|----|------|
| 现象 | `collection.count()` → `InternalError: Error loading hnsw index` |
| 原因 | C2 手动中断导致 HNSW 文件不完整；或复制进已有抽样 `chroma_db/` 混入 orphan 目录 |
| 数据 | sqlite 中 embeddings 通常仍在（本机 157,696 条未丢） |
| 处理 | C2.5a `REPAIR_HNSW=True` → `repair_chroma_hnsw()`；全量目录改用 `data/chroma_db_full/` |
| 续跑 | `RESUME=True`；HNSW 在后续 `add` 时自动重建 |
| ⚠️ 建库完成后 | **`REPAIR_HNSW=False`**；误开 repair 可能删 HNSW 二进制并留下 stale pickle（见 §9） |

### 6. C2.5：E: 仍显示读 JSONL / 中断后续跑

| 项 | 说明 |
|----|------|
| 现象 | 资源监视器见 E: 读 `oa_comm_chunks.jsonl`；但 `print(INPUT_JSONL)` 显示 D: 路径 |
| 原因（本次） | **Agent 排查脚本**（Chroma 检测、hash 等）后台未退出，占 E: 或文件句柄；**重启 Cursor 后 E: 释放** |
| 真实半解耦风险 | **C2.5a 后又跑 C0** 或 **跳过 C2.5a** → `INPUT_JSONL` 仍指 E: |
| 判断方法 | ① 打印 `INPUT_JSONL` / `PERSIST_DIR`；② 资源监视器看 **python.exe** 打开的完整路径 |
| 中断后续跑成功 | `progress.json` + sqlite 保留进度；C2.5a `REPAIR_HNSW` + `RESUME=True`；详见笔记 **Q14.4** |
| 操作纪律 | **C0→C1→C2.5a→C2.5b**；C2.5a 后**勿再跑 C0**；全量期间避免并行 Chroma 检测脚本 |

### 7. 嵌入模型：small vs base（RAG 效果）

| 项 | 说明 |
|----|------|
| 现象 | 全量跑时 GPU 显存仅用 ~1/3，疑是否应换 `bge-base-en-v1.5` |
| 速度/磁盘 | 见 Q14 讨论；base 约 2× 向量与索引体积 |
| **RAG 效果** | base 主要改善 **Recall@K 边界**；相对 MiniLM→small **非跃升**；医学领域未微调时增益有限 |
| 任务书顺序 | 检索差时先查 chunk、查询指令，**再**试不同模型 |
| 结论 | **当前全量继续 small**；全量后可对固定医学问句做 small/base **子集 A/B**；仍不足优先 rerank |
| 笔记 | 多角度分析见 `笔记/04笔记.md` **Q15** |

### 8. ClinicalBERT / 医学 embedding / 领域微调（扩展阅读）

| 项 | 说明 |
|----|------|
| 任务书 | `clinicalBERT（需自行微调）` — 非开箱检索模型 |
| 与 PMC | oa_comm 更贴 **PubMedBERT / MedCPT**；ClinicalBERT 偏 MIMIC 病历 |
| 微调要点 | query–passage 数据 → 对比学习 → 全量重嵌入 → Recall@K |
| 当前项目 | **不执行**；继续 BGE-small 全量；详见 `笔记/04笔记.md` **Q16** |

### 9. 全量建库完成后 C2.5a：`Error loading hnsw index`（stale pickle）

| 项 | 说明 |
|----|------|
| 现象 | 全量已完成后重启，C2.5a 末尾 `collection.count()` 报 `Error loading hnsw index` |
| 原因 | ① 建库完成后仍设 `REPAIR_HNSW=True`，删掉 HNSW 二进制；② Chroma 1.5.9 留下仅含 **`index_metadata.pickle`**（~261MB）、无 `data_level0.bin` 的目录；③ **sqlite 中 610 万 embedding 仍在** |
| 处理 | 删除 stale pickle（`repair_chroma_hnsw` 已增强自动清理）；`count()` 恢复 |
| 纪律 | 建库完成后 C2.5a 用 **`REPAIR_HNSW=False`**，只确认 D: 路径 |
| 笔记 | **Q17.2**；概念与 RAG 影响见 **Q18** |

### 10. C3：`The Kernel crashed` / 统计写入失败

| 项 | 说明 |
|----|------|
| 现象 | C3 无 Python traceback，Jupyter 日志 `ExitCode: 3221225477` |
| 原因 | ① `get_stats()` 内再次 `collection.count()`；② 原 C3 `import pandas` 在 Jupyter 下不稳定 |
| 处理 | C3 用 **`progress.json` / `count_embeddings_sqlite()`**；去掉 pandas |
| 操作 | 重启后 **C2.5a → builder 初始化 → C3**，勿重跑 C2.5b |
| 笔记 | **Q17.3** |

### 11. C5 元数据过滤：`Error finding id`

| 项 | 说明 |
|----|------|
| 现象 | `query(..., where_filter={"strategy": "sliding_window"})` → `Error finding id` |
| 原因 | Chroma 1.5.x 全库 metadata/HNSW 不同步（GitHub #7032）；无 `where` 的 query 正常 |
| 处理 | `query()` **over-fetch + Python 过滤**；`query_validation.json` 中 `元数据过滤生效: true` |
| 操作 | 改 `index_builder.py` 后 **`importlib.reload(index_builder)`** 再重建 `builder` |
| 笔记 | **Q17.4** |

---

## 阶段收尾：D: → E: 归档与本地清理

> **目的**：全量验证已通过，在 E: 保留权威备份；RAG 阶段挂载 **D: 暂留的 `chroma_db_full/`**。  
> **当前状态（2026-06-02）**：E: 备份已手动完成；D: **`chroma_db_full/` 保留供 RAG**；可选清理见 §4。  
> **执行前（已完成）**：`index_stats.json` 中 `total_chunks = 6107296`，C3–C5 验证通过。

### 1. 当前 `data/` 目录含义（实测 2026-06-02）

| 路径 | 体积（约） | collection | 条数 | 性质 |
|------|------------|------------|------|------|
| **`chroma_db_full/`** | **~71 GB** | `pmc_oa_comm_full` | **6,107,296** | ✅ **全量正式库**（RAG 用） |
| `chroma_db/` | ~1.8 GB | `pmc_oa_comm_full` | ~157,696 | ❌ C2 外接盘/迁移 **半成品**，已被全量库取代 |
| `chroma_repair_test/` | ~1.8 GB | `pmc_oa_comm_full` | ~158,216 | ❌ HNSW 修复 **测试残留**，与上表同类 |
| `processed/chunks_sample.jsonl` | 小 | — | 1,267 | ✅ 抽样验证输入（保留） |
| `processed/oa_comm_chunks.jsonl` | ~9 GB | — | 610 万行 | 全量 JSONL（E: 通常已有副本） |

**重要**：`chroma_db` 与 `chroma_repair_test` **不是**抽样验证库（不是 `pmc_oa_comm_sample` / 1,267 条）。抽样验证结果在 **`outputs/samples/`** 的 JSON 里；原样本 collection 曾在迁移/混放时被 **全量半成品覆盖**。

### 2. `chroma_db` vs `chroma_repair_test`：是否合并？要不要改 notebook？

| 问题 | 结论 |
|------|------|
| 两者是否相同性质？ | **是**，均为 **过时全量半成品**（~15.7 万条），互为冗余，**都不是** 1,267 样本库 |
| 是否只保留 `chroma_repair_test`？ | **不建议**。保留任一都会误导；且 **`vectorize-index.ipynb` 期望 `pmc_oa_comm_sample`**，与目录内数据不符 |
| 是否改 `vectorize-index.ipynb` 路径到 `chroma_repair_test`？ | **不需要、也不应**只改路径而不重建——改路径后仍打开错误的 `pmc_oa_comm_full` |
| 推荐做法 | **两个目录都可删除**；日后若需重跑抽样验证，仍用 notebook 默认 **`data/chroma_db/`**，**重新建库**（约数分钟，1,267 条） |

### 3. 移至 E:（备份，必做）

在资源管理器或 `robocopy` **复制整个文件夹**（不要只拷 `chroma.sqlite3`）：

| 源（D: 工程内） | 建议目标（E:） | 说明 |
|-----------------|----------------|------|
| `04...\data\chroma_db_full\` | `E:\med-llm-rag-datasets\chroma_db_full\` | **推荐单独目录名**，避免与 E: 上旧半成品 `chroma_db` 混淆 |
| 或同上 | `E:\med-llm-rag-datasets\chroma_db\` | 若确认 E: 旧 `chroma_db` 可覆盖（见下「删除」） |

**可选同步**（若 E: 尚无或需更新）：

| 源 | 目标 |
|----|------|
| `data\processed\oa_comm_chunks.jsonl` | `E:\med-llm-rag-datasets\processed\` |
| `outputs\tables\index_stats.json` | `E:\med-llm-rag-datasets\reports\` 或工程内已 git 跟踪则不必重复 |
| `outputs\tables\query_validation.json` | 同上 |

**复制后验证**（在 E: 路径执行一次 Python 或 notebook attach）：

```python
# 快速验证：条数应为 6107296
from pathlib import Path
import sys
sys.path.insert(0, r"D:\谷歌\04 向量化与索引构建\src")
from index_builder import count_embeddings_sqlite
print(count_embeddings_sqlite(r"E:\med-llm-rag-datasets\chroma_db_full"))
```

### 4. 可在 D: 删除（确认 E: 备份无误后）

| 删除对象 | 约释放 | 前提 |
|----------|--------|------|
| **`data\chroma_db_full\`** | **~71 GB** | E: 副本已验证 `6107296` 条 |
| **`data\chroma_db\`** | ~1.8 GB | 全量已完整；非样本库 |
| **`data\chroma_repair_test\`** | ~1.8 GB | 仅为修复测试残留 |
| **`data\processed\oa_comm_chunks.jsonl`** | ~9 GB | **可选**；E: 已有权威副本且短期内不在 D: 建库 |
| E: 上 **旧** `chroma_db\`（~15.7 万条半成品） | ~2 GB | 已被 `chroma_db_full` 取代 |

**勿删**：

| 保留 | 原因 |
|------|------|
| `data\processed\chunks_sample.jsonl` | 抽样 notebook 输入 |
| `outputs\` 下已生成的 JSON | 任务交付、可 git |
| E: 上新的 **`chroma_db_full\`** | 全量 RAG 权威备份 |

### 5. RAG 阶段挂载（已确定）

| 场景 | `PERSIST_DIR` | 状态 |
|------|----------------|------|
| **RAG 日常开发（当前方案）** | `D:\谷歌\04 向量化与索引构建\data\chroma_db_full\` | ✅ D: 暂留 |
| D: 已删库、从 E: 读 | `E:\med-llm-rag-datasets\chroma_db_full\` | ✅ E: 备份可用 |
| 仅用抽样做联调 | 重跑 `vectorize-index.ipynb` → `data\chroma_db\` + `pmc_oa_comm_sample` | 按需 |

统一通过 **`ChromaIndexBuilder` / `PersistentClient`** 打开，**不要**手动读 HNSW bin（见笔记 Q18）。  
调用示例与字段说明见根目录 **`README.md` →「第四阶段完成总结 → RAG 调用向量库」**。

### 6. 收尾 checklist

- [x] E: `chroma_db_full` 复制完成（手动备份，2026-06-02）
- [x] 全量验证 JSON 已生成（`outputs/tables/index_stats.json`、`query_validation.json`，可 git）
- [x] **RAG 挂载路径确定**：D: `data/chroma_db_full/` 暂留
- [ ] （可选）E: JSONL 副本确认 / 验证 JSON 额外存档
- [ ] D: 删除 `chroma_db` + `chroma_repair_test`（~3.6 GB 冗余半成品，不影响 RAG）
- [ ] （可选）D: 删除 `processed/oa_comm_chunks.jsonl`（~9 GB，E: 已有权威副本）
- [ ] （可选）E: 删除旧半成品 `chroma_db`
- [x] 撰写 `docs/向量化与索引报告.md`（2026-06-02）

> **说明**：因 RAG 阶段使用 D: 全量库，**勿删除 D: `chroma_db_full/`**，除非已改从 E: 挂载并验证 query 正常。

### 7. GitHub 上传说明

| 纳入 Git | 不纳入 Git（`.gitignore`） |
|----------|---------------------------|
| `src/`、`notebooks/`、`requirements.txt`、`schedule.md` | `data/chroma_db_full/`（~71 GB） |
| `outputs/tables/*.json`、`outputs/samples/*.json` | `data/chroma_db/`、`chroma_repair_test/` |
| `data/processed/chunks_sample.jsonl` | `data/processed/oa_comm_chunks.jsonl`（~9 GB，可选本地保留） |

克隆仓库后，RAG 阶段需在本机保留 **`D:\谷歌\04 向量化与索引构建\data\chroma_db_full\`**，或从 E: 备份复制到该路径（或修改 `PERSIST_DIR` 指向 E:）。
