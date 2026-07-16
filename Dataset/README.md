# Dataset — 跨项目共用大数据资产

本目录存放医学 RAG 工程的**全量/样本检索资产**（不进 Git）。  
**新代码请直接从这里读取**；历史阶段目录下的 `data/` 副本已迁出，仅作兼容回退。

## 布局

```text
Dataset/
├── README.md                 # 本说明
├── chroma/
│   ├── chroma_db_full/       # 全量 Chroma（~66–71 GB，collection: pmc_oa_comm_full）
│   └── chroma_db/            # 样本 Chroma（1,267，collection: pmc_oa_comm_sample）
├── bm25/
│   └── bm25_full/            # 全量 BM25 分片索引（62 片，bm25_sharded_v1）
└── processed/
    ├── oa_comm_chunks.jsonl  # 全量 chunks（~9.1 GB）
    └── oa_comm_slim.jsonl    # slim 元数据（~8.3 GB）
```

## 代码怎么引用

仓库根目录提供 [`dataset_paths.py`](../dataset_paths.py)：

```python
from dataset_paths import (
    CHROMA_FULL_DIR,
    CHUNKS_FULL_JSONL,
    SLIM_JSONL,
    BM25_FULL_DIR,
    DATASET_ROOT,
)
```

阶段 06–10 的既有入口仍走 `06/src/config.py` 的 `resolve_chroma` / `resolve_chunks_path` /
`resolve_slim_path` / `resolve_bm25_cache_dir`：**优先 Dataset**，其次旧阶段路径，再次 `E:\med-llm-rag-datasets`。

可选环境变量：

| 变量 | 作用 |
|------|------|
| `MED_RAG_DATASET_ROOT` | 覆盖 Dataset 根目录 |
| `STAGE09_BM25_FULL_DIR` | 仅覆盖 BM25 读写目录（09 构建脚本） |

## 与 E: 备份的关系

`E:\med-llm-rag-datasets\` 仍可作为外盘权威备份（体积更大，含原始包等）。  
日常开发以本目录（D:）为准；清理策略见仓库根目录 [`缓存记录.md`](../缓存记录.md)。

## 迁移状态（2026-07-16）

| 资产 | 状态 |
|------|------|
| `chroma/chroma_db`、`bm25/bm25_full`、`processed/*.jsonl` | **已迁入实体**；旧阶段路径保留目录联接或文件硬链接 |
| `chroma/chroma_db_full` | ✅ **实体已迁入**；旧 `04/.../chroma_db_full` 为目录联接 |

## 勿提交

根 `.gitignore`：`/Dataset/**`，但保留本 `README.md`。
