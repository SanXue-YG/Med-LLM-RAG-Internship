# Dataset — 跨项目共用大数据资产

本目录存放医学 RAG 工程的**全量/样本检索与篇级索引资产**（大数据不进 Git）。  
**新代码请直接从这里读取**；历史阶段目录下的 `data/` 副本仅作兼容回退。

规划类说明（可进 Git）：本 README · [`打包资产清单.md`](打包资产清单.md) · [`documents/README.md`](documents/README.md)。

## 布局

```text
Dataset/
├── README.md
├── 打包资产清单.md           # 运行时 vs 重建原料
├── chroma/
│   ├── chroma_db_full/       # 全量 Chroma（~66–71 GB，pmc_oa_comm_full）
│   └── chroma_db/            # 样本 Chroma（1,267，pmc_oa_comm_sample）
├── bm25/
│   └── bm25_full/            # 全量 BM25 分片（62 片 · ~6.1M chunks）
├── documents/
│   ├── README.md
│   ├── sample/                   # ✅ documents_sample.sqlite（1000）
│   └── full/                     # ✅ documents_full.sqlite（4,557,627 · ~11.5 GB）
└── processed/
    ├── oa_comm_chunks.jsonl  # 全量 chunks（~9.1 GB）— 建 Chroma/BM25 原料
    ├── oa_comm_slim.jsonl    # slim（~8.3 GB）— 建 documents 索引 / 旧版 06 回查
    └── chunks_sample.jsonl   # ✅ 2026-07-27 自 03 复制（不改 03 原文件）
```

## 谁在用（按阶段）

| 阶段 | 典型用法 | 模式 |
|------|----------|------|
| 04–06 | 建库 / 检索；06 现回查 **slim**（打包后改 documents sqlite） | sample 或 full |
| 08–10 | 生成 / 约束 `from_mode("sample"\|"full")` | 开发 sample；抽检 full |
| 11 | FastAPI `/qa` | 默认 sample；full 抽检 |
| **12** | 会话/统计/**文档 API**；构建 documents sqlite | sample 契约 → 阶段 5 full |

## 样本重建（chunks_sample）

```powershell
# 仅复制，不移动、不改 03/04 原文件
Copy-Item "03 文档解析与分割\data\processed\chunks_sample.jsonl" `
  "Dataset\processed\chunks_sample.jsonl"
```

来源：`03 .../chunks_sample.jsonl`（04 目录有同内容副本）。  
篇级样本/全量索引构建命令见 [`documents/README.md`](documents/README.md)（12 脚本落地后补全）。

## 代码怎么引用

```python
from dataset_paths import (
    CHROMA_FULL_DIR,
    CHROMA_SAMPLE_DIR,
    CHUNKS_FULL_JSONL,
    CHUNKS_SAMPLE_JSONL,
    SLIM_JSONL,
    BM25_FULL_DIR,
    DOCUMENTS_FULL_DIR,
    DOCUMENTS_FULL_SQLITE,
    DOCUMENTS_SAMPLE_DIR,
    DOCUMENTS_SAMPLE_SQLITE,
    COLLECTION_FULL,
    COLLECTION_SAMPLE,
    DATASET_ROOT,
)
```

| 变量 | 作用 |
|------|------|
| `MED_RAG_DATASET_ROOT` | 覆盖 Dataset 根 |
| `STAGE09_BM25_FULL_DIR` | 仅覆盖 BM25 |
| `MED_RAG_RETRIEVAL_MODE` | `sample` \| `full` |

## 全量就绪口径（问答）

1. `chroma/chroma_db_full` 可读（`pmc_oa_comm_full`）  
2. `bm25/bm25_full/manifest.json` → `bm25_sharded_v1` + `completed`  
3. （建议）`processed/oa_comm_chunks.jsonl` 存在  
4. ✅ `documents/full/documents_full.sqlite` + `manifest_full.status=completed`（4,557,627 篇）  
5. Ollama 可用  

## 篇级索引构建（documents）

产物分目录：`documents/sample/` 与 `documents/full/`。说明见 [`documents/README.md`](documents/README.md)。增量补丁见 [`（未来优化）打包后数据更新`](../（未来优化）打包后数据更新/schedule.md)。

## 迁移状态

| 资产 | 状态 |
|------|------|
| chroma / bm25 / slim / chunks 全量 | ✅ 已在 Dataset（2026-07-16） |
| `chunks_sample.jsonl` | ✅ **2026-07-27 复制**自 03；03/04 原文件保留 |
| `documents_*.sqlite` | ✅ sample（1000）+ ✅ full（4,557,627 · 2026-07-27） |
| 11 full live | ✅ 已抽检 |

## 勿提交

`/Dataset/**` ignore；例外：本 README、`打包资产清单.md`、`documents/README.md`。  
大数据与 sqlite 本体本地保留；重建见各 README / [`（未来优化）打包后数据更新`](../（未来优化）打包后数据更新/schedule.md)。
