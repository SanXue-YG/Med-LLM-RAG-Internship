# Dataset/documents — 篇级文档索引（全库 / 样本）

> **定位**：从 `processed/oa_comm_slim.jsonl` 离线构建的 **篇级元数据索引**（推荐 SQLite），供：  
> 1. **12 `/documents` API**（列表 / 按 pmcid 查询）  
> 2. **未来打包后替代 06 对 slim JSONL 的回查**（`pub_year` / `journal` → recency / authority）  
>  
> **不是**检索库：向量/BM25 仍用 `chroma/` + `bm25/`（基于 **chunks**）。

本目录产物 **不进 Git**（随 `/Dataset/**` ignore）；重建步骤见下文与 [`../打包资产清单.md`](../打包资产清单.md)。

---

## 计划落盘文件

| 文件 | 用途 | 状态 |
|------|------|------|
| `documents_full.sqlite` | 全库篇级索引（~455 万篇）；**运行时单库** | ⏳ 12 阶段前期构建 |
| `documents_sample.sqlite` | 样本篇级索引（与 `chunks_sample` 文献对齐） | ⏳ 12 与全量脚本同批生成，供阶段 5 前快速验 API |
| `manifest.json` | 构建来源、schema 版本、行数、耗时、`batch_size` | 随构建写入 |
| `progress.json` | **断点续建**：已处理 slim 行号 / 已写入篇数 | 构建中写入；完成可保留或归档 |
| `README.md` | 本说明 | ✅ |

> 过渡期也可用 `documents_sample.json`；**目标形态为 SQLite**，与打包友好口径一致。  
> 构建期可另有临时 WAL/`*.sqlite.tmp`；**不**把「多物理分库」作为运行时默认形态（见下节）。

---

## 构建策略：对标 BM25 分片，但改成「逻辑分片」

### 可行性结论

| | BM25（`bm25_sharded_v1`） | 文档索引（本目录） |
|--|--------------------------|-------------------|
| 为何分片 | 单体 `BM25Okapi` 内存峰值极高；**查询也要逐片加载** | 全量 ~455 万篇写 sqlite **内存通常不是瓶颈**；墙钟长（0.5–2h+）→ 怕中断 |
| 分片形态 | 物理：`shard_00000.pkl` … + `progress.json` | **逻辑**：单库 + **按批 COMMIT** + `progress.json` |
| 运行时产物 | 多文件目录 | **`documents_*.sqlite` 单文件**（打包友好） |
| 断点续建 | 跳过已完成 shard / `processed_lines` | 跳过已处理 slim **行号**，继续 `INSERT OR REPLACE` |
| 新文献补充 | 分片 BM25 增量难，多定期全量 | **天然友好**：增量 slim → upsert 同一库（见未来优化补丁） |

→ **要学 BM25 的是「流式批处理 + progress 断点 + manifest 校验」**，不是把篇级元数据拆成几十个 sqlite 再合并查询。  
物理多分库（`documents_full/shard_*.sqlite`）仅在「多进程并行建库再 merge」时可选；**12 `/documents` 与 06 回查默认仍读合并后的单库**。

### 推荐构建算法（`build_documents_index.py`）

```text
1. 打开/创建 documents_{mode}.sqlite，建表 + PRIMARY KEY(pmcid)
2. 若 resume 且 progress.json 与 source_slim 路径/mtime、batch_size、schema_version 兼容：
     skip_lines = progress.processed_lines
   否则从 0 开始（或 --no-resume 删 progress 重建）
3. 流式读 oa_comm_slim.jsonl：
     每 batch_size 行（建议默认 50_000～100_000）：
       BEGIN; 批量 INSERT OR REPLACE; COMMIT
       写 progress.json：processed_lines / valid_rows / last_pmcid / updated_at
4. 完成后写 manifest.json：status=completed、row_count、source_*、batch_size、schema_version
5. CLI：--mode sample|full · --batch-size · --resume/--no-resume · --status · --limit（smoke）
```

样本模式：可只写入 `chunks_sample` 涉及的 pmcid（或小集合），同样走批提交（样本体量小，断点非必须但接口一致）。

### 与增量补丁的衔接

- **断点续建** = 同一次全量构建中途恢复（按 slim **行偏移**）。  
- **补丁增补** = 另一次任务：读 **增量 slim/jsonl**（或「不在库中的 pmcid」），仍 `INSERT OR REPLACE`，更新 `manifest.row_count` / `updated_at` / `patch_manifest`。  
二者共用同一 upsert 内核，避免两套写入逻辑。详见 [`（未来优化）打包后数据更新/schedule.md`](../（未来优化）打包后数据更新/schedule.md)。

---

## 为何需要这些字段（依据 06 + 12）

### 06 回查在干什么

`06/.../rerank_features.py` 的 `SlimMetadataLookup` 按检索命中的 `doc_id`（= **pmcid**）从 slim **扫库回查**：

| 读出的字段 | 用途 |
|------------|------|
| `pub_year` | `recency_score`：越新分越高；可配合 query 的 `year_gte` 降权过旧文献 |
| `journal` | `authority_score`：按期刊名规则表打权威分（Nature/Lancet/…） |

二者与向量相关分加权，影响 **重排序最终顺序**。  
chunk 元数据里 **没有**可靠的 `pub_year`，所以必须有篇级源（现为 slim；打包后改为本索引）。

### 12 `/documents` 要什么

任务书 `DocumentIn`：`doc_id, title, abstract, journal, pub_date` 等。

### 定稿：索引表建议字段

| 列 | 来源（slim） | 06 回查 | `/documents` | 备注 |
|----|--------------|---------|--------------|------|
| `pmcid` | `pmcid` | ✅ 键 | ✅ = `doc_id` | **PRIMARY KEY** |
| `pmid` | `pmid` | | 可选 | |
| `title` | `title` | | ✅ | |
| `abstract` | `abstract` | | ✅（列表可截断） | 体积大；可另表或压缩策略 |
| `journal` | `journal` | ✅ | ✅ | |
| `pub_year` | `pub_year` | ✅ | 可选 | INTEGER |
| `pub_date` | `pub_date` | | ✅ | 文本 ISO/原文 |
| `n_chars_abstract` | 同名 | | 可选 | 调试 |
| `schema_version` | 构建写入 | | | 便于补丁升级 |
| `updated_at` | 构建/补丁写入 | | | 增量用 |

`manifest.json` 另记：`source_slim_path`、`source_mtime`、`row_count`、`built_at`、`builder`、`schema_version`。

---

## 样本 vs 全量

| | 样本 | 全量 |
|--|------|------|
| 库文件 | `documents_sample.sqlite` | `documents_full.sqlite` |
| 文献范围 | `chunks_sample` 涉及的 pmcid ∪ 小集合 | slim 全表 ~455 万 |
| 谁用 | 12 阶段 **0–4** 契约（smoke C0.5 产出） | 12 **阶段 5** + 打包；可与 1–4 **并行建库** |
| Notebook | `api-ops-smoke.ipynb` **C0.5** | `api-ops-full.ipynb` **F0**（进度可视化）或 CLI 后台 |

构建脚本：`12 .../scripts/build_documents_index.py` → `dataset_paths`。  
**节奏**：先 C0.5 建 sample → 立刻开写阶段 1–4；F0/CLI 建 full（可过夜/后台）；full 完成后再开阶段 5 全量仿真。
---

## 重建（本机）

```text
# 1）确认 slim 存在
Dataset/processed/oa_comm_slim.jsonl

# 2）样本（阶段 0 · smoke C0.5；进 1–4 前必做）
cd "12 服务化与接口开发第二部分"
python scripts/build_documents_index.py --mode sample

# 3）全量（api-ops-full F0 可视化，或终端后台；与 1–4 并行）
python scripts/build_documents_index.py --mode full --batch-size 50000
# 中断后续跑同一命令即可续建；查看进度：
python scripts/build_documents_index.py --mode full --status
# 强制从头：
python scripts/build_documents_index.py --mode full --no-resume
```

增量补丁 / 全量重建策略见仓库 [`（未来优化）打包后数据更新/schedule.md`](../（未来优化）打包后数据更新/schedule.md)。
---

## 与打包的关系

运行时推荐携带：`documents_full.sqlite`（+ manifest），**不必**再为回查携带整份 slim JSONL。  
slim / chunks JSONL 可作为 **重建原料** 外置。详见 [`../打包资产清单.md`](../打包资产清单.md)。
