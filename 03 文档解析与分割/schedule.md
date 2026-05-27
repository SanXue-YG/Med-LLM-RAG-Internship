# 03 文档解析与分割 — 执行计划

> **状态：✅ 已完成**（2026-05-27）

---

## 与第二阶段的衔接关系

### 第二阶段已产出（直接复用）

| 产出物 | 路径 | 用途 |
|--------|------|------|
| slim JSONL | `E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl` | **本阶段输入** |
| 分割策略配置 | `02 数据处理/outputs/tables/chunk_strategy_config.json` | 分割参数 |
| Tokenizer | `sentence-transformers/all-MiniLM-L6-v2` | 继续使用 |

### 数据流

```
第二阶段 oa_comm_slim.jsonl (4,557,627 篇)
    ↓ 读取 title + abstract
第三阶段分割处理
    ↓ 单块 85.5% / 多块 14.5%
输出 oa_comm_chunks.jsonl (6,107,296 chunks)
```

---

## 执行步骤

### 阶段 0：环境与配置 ✅

- [x] 创建目录结构：`src/`、`notebooks/`、`outputs/`、`data/`
- [x] 复用第二阶段环境 `med-rag-verify`
- [x] 读取分割策略配置 `chunk_strategy_config.json`

**已创建文件：**

| 文件 | 说明 |
|------|------|
| `notebooks/doc-chunking.ipynb` | 验证样本分析 |
| `notebooks/doc-chunking-full.ipynb` | 全量处理 |
| `src/chunker.py` | 核心分割模块 |
| `requirements.txt` | 依赖说明 |

### 阶段 1：数据加载（任务§1）✅

- [x] 从 slim JSONL 流式读取
- [x] 字段映射：`pmcid` → `doc_id`，`title` → `source_title`
- [x] 拼接检索文本：`title + "\n\n" + abstract`

### 阶段 2：实施分割策略（任务§2）✅

- [x] 加载 tokenizer：`sentence-transformers/all-MiniLM-L6-v2`
- [x] 初始化分割器：`RecursiveCharacterTextSplitter(chunk_size=400, overlap=80)`
- [x] 实现智能分割：≤512 单块，>512 滑动窗口
- [x] 生成 chunk_id：单块用 pmcid，多块用 `pmcid_chunk{i}`

### 阶段 3：分批处理与保存（任务§3）✅

- [x] 流式处理 450 万文档
- [x] 断点续传支持（progress.json）
- [x] 输出到 JSONL 格式

### 阶段 4：预览与统计（任务§4）✅

- [x] 抽样预览 chunk 结构
- [x] 统计报告：总 chunk 数、平均 chunk/doc、token 分布

### 阶段 5：质量验证（任务§5）✅

- [x] Token 超限检查：0 个超限
- [x] 空文本/极短文本检查：通过
- [x] 多块分割重叠检查：正确

---

## 处理结果

### 全量数据

| 指标 | 数值 |
|------|------|
| 输入文档 | 4,557,627 |
| 输出 chunks | **6,107,296** |
| 单块文档 | 3,894,927（85.5%） |
| 多块文档 | 662,700（14.5%） |
| 平均 chunk/doc | 1.34 |

### 质量验证（抽样 1000）

| 检查项 | 结果 |
|--------|------|
| Token 超限 | 0 |
| 空文本 | 0 |
| 极短文本 | 1 |
| Token 均值 | 285.18 |
| Token P95 | 472.0 |
| Token 最大 | 512 |

---

## 交付产物清单

| 产物 | 路径 | Git |
|------|------|-----|
| **全量 chunks** | `E:\...\oa_comm_chunks.jsonl` | ❌ 外接硬盘 |
| **验证样本** | `data/processed/chunks_sample.jsonl` | ✅ |
| **处理报告** | `docs/文档分割处理报告.md` | ✅ |
| **全量统计** | `outputs/tables/chunking_stats.json` | ✅ |
| **全量质量报告** | `outputs/tables/quality_report.json` | ✅ |
| **验证样本统计** | `outputs/samples/chunking_stats_sample.json` | ✅ |
| **验证样本质量报告** | `outputs/samples/quality_report_sample.json` | ✅ |

---

## 目录结构

```
03 文档解析与分割/
├── 任务.txt                    # 老师任务书
├── schedule.md                 # 本文件
├── requirements.txt            # 依赖说明
├── docs/
│   └── 文档分割处理报告.md      # 正式交付报告
├── src/
│   ├── __init__.py
│   └── chunker.py              # 核心分割模块
├── notebooks/
│   ├── doc-chunking.ipynb      # 验证样本分析
│   └── doc-chunking-full.ipynb # 全量处理
├── data/
│   └── processed/
│       └── chunks_sample.jsonl # 验证样本（1267 chunks）
└── outputs/
    ├── tables/                 # 全量统计
    │   ├── chunking_stats.json
    │   └── quality_report.json
    └── samples/                # 验证样本统计
        ├── chunking_stats_sample.json
        └── quality_report_sample.json
```

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-05-27 09:35 | 环境配置完成，创建 notebook 和 src 模块 |
| 2026-05-27 10:03 | 验证样本（1000篇）处理完成，质量验证通过 |
| 2026-05-27 12:55 | 全量处理完成（6,107,296 chunks） |
| 2026-05-27 13:07 | 验证样本报告独立生成，准备 git 提交 |
| **2026-05-27 13:15** | **第三阶段全部完成** |
