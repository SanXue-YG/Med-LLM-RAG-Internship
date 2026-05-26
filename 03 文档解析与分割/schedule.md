# 03 文档解析与分割 — 执行计划

## 与第二阶段的衔接关系

### 第二阶段已产出（可直接复用）

| 产出物 | 路径 | 用途 |
|--------|------|------|
| slim JSONL | `E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl` | **直接作为本阶段输入** |
| 分割策略配置 | `02 数据处理/outputs/tables/chunk_strategy_config.json` | 分割参数来源 |
| 策略验证结果 | `02 数据处理/outputs/tables/chunk_strategy_summary.csv` | 参考：85% single / 14% multi |
| Tokenizer | `sentence-transformers/all-MiniLM-L6-v2` | 继续使用 |

### 复用策略

```
第二阶段 slim JSONL 结构：
{pmcid, pmid, title, abstract, journal, pub_year, pub_date, n_chars_abstract, n_chars_body}

    ↓ 直接读取（无需重新解析XML）

第三阶段输入 → 分割 → 输出 chunks
```

**关键**：第二阶段的 `oa_comm_slim.jsonl` 已包含 ~500万篇文献的 title + abstract，本阶段无需再访问 XML 原文件。

---

## 执行步骤

### 阶段 0：环境与配置（~30 min）

- [ ] 创建 `03 文档解析与分割/src/` 目录结构
- [ ] 复制/链接第二阶段的配置文件：
  - `chunk_strategy_config.json` → 分割参数
- [ ] 安装依赖（应与02共用环境 `med-rag-verify`）：
  - `langchain-text-splitters`（RecursiveCharacterTextSplitter）
  - `sentence-transformers`（tokenizer）
- [ ] 定义输入/输出路径常量

### 阶段 1：数据加载与清洗（任务§1）

- [ ] 从 slim JSONL 流式读取（避免一次性加载500万行）
- [ ] 字段映射：
  | slim JSONL | 第三阶段字段 |
  |------------|-------------|
  | `pmcid` | `doc_id` |
  | `title` | `source_title` |
  | `title + abstract` | 待分割文本 |
- [ ] 跳过无 abstract 的记录（第二阶段已过滤，双重保险）
- [ ] 生成 `doc_id`：直接使用 `pmcid`（已唯一）

### 阶段 2：实施分割策略（任务§2）

复用第二阶段验证的策略参数：

```python
# 来自 chunk_strategy_config.json
CHUNK_SIZE = 400       # tokens
CHUNK_OVERLAP = 80     # tokens
TOKEN_LIMIT = 512      # 单chunk上限
```

分割逻辑：

```python
def process_document(doc):
    text = f"{doc['title']}\n\n{doc['abstract']}"
    token_count = count_tokens(text)
    
    if token_count <= TOKEN_LIMIT:
        # 策略 a: 不分割（约85%文档）
        return [create_single_chunk(doc, text, token_count)]
    else:
        # 策略 b: RecursiveCharacterTextSplitter（约14%文档）
        return split_with_overlap(doc, text)
```

输出 chunk 结构：

```json
{
  "chunk_id": "PMC12345678_0",
  "text": "...",
  "doc_id": "PMC12345678",
  "chunk_index": 0,
  "total_chunks": 1,
  "source_title": "Article Title",
  "token_count": 342
}
```

### 阶段 3：分批处理与保存（任务§3）

考虑500万文档规模，采用**分批 + 断点续传**（复用第二阶段模式）：

- [ ] 按 JSONL 行数分批（如每 50 万行一个 shard）
- [ ] 每个 shard 处理后立即保存：`chunks_shard_00.parquet`
- [ ] 进度保存到 `progress.json`，支持中断续传
- [ ] 最终合并或保持分片（根据下游需求）

输出格式选择：
- **Parquet**（推荐）：列式存储，压缩率高，适合后续向量化批处理
- JSONL：兼容性好，但文件较大

### 阶段 4：预览与统计（任务§4）

- [ ] 抽样预览 10-20 条 chunks
- [ ] 统计报告：
  - 总 chunk 数
  - 平均 chunk/doc 比例
  - token 分布直方图
  - 单块 vs 多块文档比例

### 阶段 5：质量验证（任务§5）

- [ ] 抽样检查（100-200 条）：
  - 是否包含标题
  - 文本是否被不完整截断（句子/词中断）
  - token 数是否在限制内
- [ ] 多块文档专项检查：
  - 重叠部分是否正确
  - 块序号是否连续
- [ ] 导出验证报告

---

## 目录结构规划

```
03 文档解析与分割/
├── 任务.txt
├── schedule.md
├── src/
│   ├── __init__.py
│   ├── config.py          # 路径和分割参数
│   ├── chunker.py         # 核心分割逻辑
│   ├── pipeline.py        # 分批处理流水线
│   └── validation.py      # 质量验证
├── notebooks/
│   └── chunk-pipeline.ipynb  # 主执行notebook
├── outputs/
│   ├── chunks/            # 分片输出
│   │   ├── chunks_shard_00.parquet
│   │   ├── ...
│   │   └── progress.json
│   ├── stats/             # 统计报告
│   │   ├── chunk_stats.json
│   │   └── token_distribution.png
│   └── validation/        # 验证结果
│       └── quality_report.json
└── data/                  # 符号链接或配置指向
    └── → E:\med-llm-rag-datasets\processed\
```

---

## 交付产物清单

| 产物 | 格式 | 说明 |
|------|------|------|
| 文本块数据集 | Parquet (分片) | 不上交，供后续向量化使用 |
| 处理配置 | JSON | 分割参数、输入输出路径 |
| 统计报告 | JSON + 图表 | 块数、分布、chunk/doc比例 |
| 质量验证报告 | JSON | 抽样检查结果、问题记录 |

---

## 预估工作量

| 阶段 | 预估时间 |
|------|----------|
| 环境准备 | 0.5h |
| 代码实现 | 2-3h |
| 全量运行（500万文档） | 2-4h（取决于磁盘IO） |
| 验证与报告 | 1h |
| **合计** | **6-8h** |

---

## 风险与应对

1. **内存不足**：流式处理 + 分批写入，避免全量加载
2. **运行中断**：断点续传机制（参考02阶段实现）
3. **磁盘空间**：Parquet 压缩 + 预估空间需求（约 5-10 GB）

---

## 待第二阶段完成后启动

当 `02 数据处理` 的 B3 完成后：
1. 确认 `oa_comm_slim.jsonl` 已生成
2. 记录最终行数（预计 400-500 万）
3. 开始本阶段执行
