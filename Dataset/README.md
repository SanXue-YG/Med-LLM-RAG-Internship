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
│   └── bm25_full/            # 全量 BM25 分片索引（62 片，bm25_sharded_v1 · ~6.1M chunks）
└── processed/
    ├── oa_comm_chunks.jsonl  # 全量 chunks（~9.1 GB）
    └── oa_comm_slim.jsonl    # slim 元数据（~8.3 GB）
```

## 谁在用（按阶段）

| 阶段 | 典型用法 | 模式 |
|------|----------|------|
| 04–06 | 建库 / 检索 pipeline 读路径 | sample 或 full |
| 08–10 | 生成 / 约束流水线 `from_mode("sample"\|"full")` | 开发多用 sample；抽检可用 full |
| **11 服务化** | FastAPI `RagService` → 10 `ConstrainedGenerationPipeline` | 进程默认 **sample**；全量连通抽检显式 `full`（见下） |

阶段 11 全量 API 抽检（不改本目录内容，只读）：

```text
# 资源自检（不冷启管线）
# app.probe.probe_full_dataset → chroma_db_full + bm25_full manifest + Ollama

# 跑通（主线程 full + 可选 HTTP 探针）
cd "11 服务化与接口开发第一部分"
python scripts/run_full_api_smoke.py
# 产物：outputs/reports/full_api_smoke*.json/png（代码仓内，非 Dataset）
```

服务进程切全量（须**重启**，禁止每请求换库）：

| 变量 | 作用 |
|------|------|
| `MED_RAG_RETRIEVAL_MODE=full` | 11 / 通用检索模式（优先） |
| `STAGE11_RETRIEVAL_MODE=full` | 11 备用覆盖 |

## 代码怎么引用

仓库根目录提供 [`dataset_paths.py`](../dataset_paths.py)：

```python
from dataset_paths import (
    CHROMA_FULL_DIR,
    CHROMA_SAMPLE_DIR,
    CHUNKS_FULL_JSONL,
    SLIM_JSONL,
    BM25_FULL_DIR,
    COLLECTION_FULL,
    COLLECTION_SAMPLE,
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
| `MED_RAG_RETRIEVAL_MODE` | `sample` \| `full`（11 服务与部分管线） |

## 全量抽检就绪口径（11 / 笔记 Q3）

下列同时满足时，才建议跑 `from_mode("full")` 或阶段 11 `run_full_api_smoke`：

1. `chroma/chroma_db_full` 可读（collection 预期 `pmc_oa_comm_full`）  
2. `bm25/bm25_full/manifest.json` → `format=bm25_sharded_v1` 且 `status=completed`（62 片）  
3. （建议）`processed/oa_comm_chunks.jsonl` 存在  
4. Ollama 可用（11 默认模型见阶段配置，如 `deepseek-r1:7b`）

## 与 E: 备份的关系

`E:\med-llm-rag-datasets\` 仍可作为外盘权威备份（体积更大，含原始包等）。  
日常开发以本目录（D:）为准；清理策略见仓库根目录 [`缓存记录.md`](../缓存记录.md)。

## 迁移状态（2026-07-16；11 消费确认 2026-07-25）

| 资产 | 状态 |
|------|------|
| `chroma/chroma_db`、`bm25/bm25_full`、`processed/*.jsonl` | **已迁入实体**；旧阶段路径保留目录联接或文件硬链接 |
| `chroma/chroma_db_full` | ✅ **实体已迁入**；旧 `04/.../chroma_db_full` 为目录联接 |
| 阶段 11 full live | ✅ 已用本目录 full 资产跑通连通抽检（见 `11 .../docs/服务化接口报告.md` §4） |

## 勿提交

根 `.gitignore`：`/Dataset/**`，但保留本 `README.md`。  
勿把 Chroma/BM25/JSONL 大文件加入 Git；阶段 11 的 `outputs/reports/` 为小体积抽检产物，按需提交。
