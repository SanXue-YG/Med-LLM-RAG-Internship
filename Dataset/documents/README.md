# Dataset/documents — 篇级文档索引（全库 / 样本）

> **定位**：从 `processed/oa_comm_slim.jsonl` 离线构建的 **篇级元数据索引**（推荐 SQLite），供：  
> 1. **12 `/documents` API**（列表 / 按 pmcid 查询）  
> 2. **未来打包后替代 06 对 slim JSONL 的回查**（`pub_year` / `journal` → recency / authority）  
>  
> **不是**检索库：向量/BM25 仍用 `chroma/` + `bm25/`（基于 **chunks**）。

本目录产物 **不进 Git**（随 `/Dataset/**` ignore）；重建步骤见下文与 [`../打包资产清单.md`](../打包资产清单.md)。

---

## 目录布局（sample / full 分开放）

```text
Dataset/documents/
├── README.md                 # 本说明
├── sample/                   # 样本索引（阶段 0–4）
│   ├── documents_sample.sqlite   # ✅ 1000 篇
│   ├── manifest_sample.json
│   └── progress_sample.json
└── full/                     # 全库索引（阶段 5 + 打包）
    ├── documents_full.sqlite     # ✅ 4,557,627 篇 · ~11.5 GB（2026-07-27）
    ├── manifest_full.json        # status=completed
    └── progress_full.json
```

| 路径 | 用途 | 状态 |
|------|------|------|
| `sample/documents_sample.sqlite` | 与 `chunks_sample` pmcid 对齐 | ✅ 1000 篇 |
| `sample/manifest_sample.json` | sample 构建元数据 | ✅ |
| `full/documents_full.sqlite` | 全库篇级索引；**运行时单库** | ✅ **4,557,627** 篇 |
| `full/progress_full.json` | 全量断点续建记录 | ✅（构建期写入） |
| `full/manifest_full.json` | 全量完成标志 `status=completed` | ✅ |

> **落盘形态说明**：与 BM25 的 `shard_*.pkl` 不同，文档索引采用 **逻辑分片**（按批 COMMIT + progress 断点），完成后目录里只有 **一个** sqlite + manifest/progress，**不会**出现多个物理分块文件。

代码常量：`dataset_paths.DOCUMENTS_SAMPLE_DIR` / `DOCUMENTS_FULL_DIR` / `DOCUMENTS_*_SQLITE`。

---

## 构建策略：对标 BM25 分片，但改成「逻辑分片」

### 可行性结论

| | BM25（`bm25_sharded_v1`） | 文档索引（本目录） |
|--|--------------------------|-------------------|
| 为何分片 | 单体 `BM25Okapi` 内存峰值极高；**查询也要逐片加载** | 全量 ~455 万篇写 sqlite **内存通常不是瓶颈**；墙钟长（0.5–2h+）→ 怕中断 |
| 分片形态 | 物理：`shard_00000.pkl` … + `progress.json` | **逻辑**：单库 + **按批 COMMIT** + `progress_*.json` |
| 运行时产物 | 多文件目录 | **各 mode 目录下单个 sqlite**（打包友好） |
| 断点续建 | 跳过已完成 shard / `processed_lines` | 跳过已处理 slim **行号**，继续 `INSERT OR REPLACE` |
| 新文献补充 | 分片 BM25 增量难，多定期全量 | **天然友好**：增量 slim → upsert 同一库 |

→ **要学 BM25 的是「流式批处理 + progress 断点 + manifest 校验」**，不是把篇级元数据拆成几十个 sqlite 再合并查询。  
**sample 与 full 用子目录隔离**，避免产物混放。

### 推荐构建算法（`build_documents_index.py`）

```text
1. 打开/创建 {sample|full}/documents_{mode}.sqlite，建表 + PRIMARY KEY(pmcid)
2. 若 resume 且 progress_{mode}.json 与 source_slim 路径/mtime、batch_size、schema_version 兼容：
     skip_lines = progress.processed_lines
   否则从 0 开始（或 --no-resume 删 progress 重建）
3. 流式读 oa_comm_slim.jsonl：
     每 batch_size 行（建议默认 50_000～100_000）：
       BEGIN; 批量 INSERT OR REPLACE; COMMIT
       写 {mode}/progress_{mode}.json
4. 完成后写 {mode}/manifest_{mode}.json：status=completed、…
5. CLI：--mode sample|full · --batch-size · --resume/--no-resume · --status · --limit
```

样本模式：只写入 `chunks_sample` 涉及的 pmcid。

### 与增量补丁的衔接

- **断点续建** = 同一次全量构建中途恢复（按 slim **行偏移**）。  
- **补丁增补** = 读增量 slim → upsert 进 `full/documents_full.sqlite`。  
详见 [`（未来优化）打包后数据更新/schedule.md`](../（未来优化）打包后数据更新/schedule.md)。

---

## 为何需要这些字段（依据 06 + 12）

### 06 回查在干什么

`06/.../rerank_features.py` 的 `SlimMetadataLookup` 按检索命中的 `doc_id`（= **pmcid**）从 slim **扫库回查**：

| 读出的字段 | 用途 |
|------------|------|
| `pub_year` | `recency_score` |
| `journal` | `authority_score` |

### 12 `/documents` 要什么

任务书 `DocumentIn`：`doc_id, title, abstract, journal, pub_date` 等。

### 定稿：索引表建议字段

| 列 | 来源（slim） | 06 回查 | `/documents` | 备注 |
|----|--------------|---------|--------------|------|
| `pmcid` | `pmcid` | ✅ 键 | ✅ = `doc_id` | **PRIMARY KEY** |
| `pmid` | `pmid` | | 可选 | |
| `title` | `title` | | ✅ | |
| `abstract` | `abstract` | | ✅ | |
| `journal` | `journal` | ✅ | ✅ | |
| `pub_year` | `pub_year` | ✅ | 可选 | INTEGER |
| `pub_date` | `pub_date` | | ✅ | |
| `n_chars_abstract` | 同名 | | 可选 | |
| `schema_version` | 构建写入 | | | |
| `updated_at` | 构建/补丁写入 | | | |

---

## 样本 vs 全量

| | 样本 | 全量 |
|--|------|------|
| 目录 | `documents/sample/` | `documents/full/` |
| 库文件 | `documents_sample.sqlite` | `documents_full.sqlite` |
| 文献范围 | `chunks_sample` 的 pmcid（1000） | slim 全表 ~455 万 |
| 谁用 | 12 阶段 **0–4** | 12 **阶段 5** + 打包 |
| Notebook | `api-ops-smoke` C0.5（默认只验收） | `api-ops-full` **F0** ✅ 已跑通 |
| 实测 | 1000 篇 | **4,557,627** 篇 · ≈134 s · ≈11.5 GB |

---

## 重建（本机）

```text
# 样本（一般已建好；仅需重建时）
cd "12 服务化与接口开发第二部分"
python scripts/build_documents_index.py --mode sample --no-resume

# 全量（写入 documents/full/；可断点）
python scripts/build_documents_index.py --mode full --batch-size 50000
python scripts/build_documents_index.py --mode full --status
```

或打开 `notebooks/api-ops-full.ipynb`，将 `RUN_FULL_BUILD = True` 后跑 F0。

---

## 与打包的关系

运行时推荐携带：`documents/full/documents_full.sqlite`（+ manifest），**不必**再为回查携带整份 slim JSONL。  
详见 [`../打包资产清单.md`](../打包资产清单.md)。
