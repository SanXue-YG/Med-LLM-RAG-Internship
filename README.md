# 医学 RAG 实习工程 — 总说明

基于 PMC 开放获取文献（`oa_comm`）的本地 LLM + RAG 可行性验证与数据评估项目。工程按阶段拆分目录，每阶段有独立任务书、计划、依赖与 Jupyter 入口。

> **给老师 / 审阅者**：各阶段**任务原文**见各目录下 `任务.txt`；**执行计划与进度**见各目录 `schedule.md`；**正式分析结论**见各阶段 `docs/`
---

## README 结构说明

> 本表供快速定位与后续维护 README 时使用；**新增阶段请按相同板块更新对应章节**。

| 章节 | 作用 | 更新时机 |
|------|------|----------|
| **文件目录结构** | 仓库顶层目录树与各阶段文件夹 | 新增/重命名阶段目录时 |
| **阶段一览** | 各阶段状态、任务书、计划、notebook、依赖的一览表 | 每阶段启动或收尾时 |
| **各阶段完成总结** | 各阶段任务、项目位置、关键结果、产出索引（**不写冗长实现细节**） | 阶段收尾时追加/修订对应小节 |
| **Python 环境与依赖** | Conda 环境、分阶段 `requirements.txt`、根目录一键依赖 | 某阶段引入新包时 |
| **本地部署指南** | 从 GitHub 克隆后的搭建步骤；`.gitignore` 与未上传大文件说明 | 数据路径或 ignore 规则变化时 |
| **各阶段交付物速查** | 精炼成果、⚠️ 边界、API、**schedule 后续开发注意** | 阶段收尾；schedule 有新增注意事项时 |
| **笔记目录** | 个人学习 Q&A（非正式交付） | 写新笔记时 |
| **更新记录** | 按时间线的变更日志；**当前阶段条目加粗**，阶段结束后整合为普通条目 | 阶段进行中实时更新 |

**阅读顺序建议**：新人 → 阶段一览 → 本地部署指南 → 各阶段交付物速查（**产品 Demo** 见 [`Med-RAG/`](Med-RAG/)；分阶段开发 API 仍以 **12** 为 ops 入口、**11** 为问答底座）→ Dataset [`打包资产清单`](Dataset/打包资产清单.md) · [Google Drive 共享](https://drive.google.com/drive/folders/1uK-2nbpOAWH61pWWrArpR8fdUzUihZ7H?usp=sharing) → 对应 `schedule.md` / `Med-RAG/docs/`。

---

## 文件目录结构

```text
谷歌/
├── README.md                 # 本文件（项目总说明）
├── dataset_paths.py          # 统一 Dataset 路径常量（新代码优先 import）
├── 缓存记录.md               # 模型/缓存/大数据清理与迁移对照
├── Dataset/                  # 跨项目共用大数据（不进 Git；见 Dataset/README.md）
├── requirements.txt          # 依赖安装清单（说明）；一键安装见 install_all_requirements.ps1
├── install_all_requirements.ps1  # 按阶段顺序 pip install（推荐）
├── .gitignore                # Git 忽略规则
├── setup_windows_env.ps1     # Windows 环境一键配置脚本
├── setup_stage04_gpu.ps1     # 04 全量向量化：CUDA 版 PyTorch 补充安装
├── scripts/                  # 仓库级脚本（如 chroma 实体化迁移）
├── 01 验证模型/              # 阶段 1：本地 LLM + PMC 数据源验证（✅）
├── 02 数据处理/              # 阶段 2：数据加载与评估（✅）
├── 03 文档解析与分割/        # 阶段 3：文本分割（✅）
├── 04 向量化与索引构建/      # 阶段 4：嵌入 + ChromaDB 索引（✅ 全量完成）
├── 05 检索系统开发第一部分/  # 阶段 5：查询理解与增强（✅）
├── 06 检索系统开发第二部分/  # 阶段 6：多路检索 + 融合 + 重排序（✅）
├── 07 生成模块与提示词工程第一部分/  # 阶段 7：上下文组装 + Prompt 模板（✅）
├── 08 生成模块与提示词工程第二部分/  # 阶段 8：Ollama 生成 + 端到端流水线（✅）
├── 09 生成答案评估，缓存策略与批量处理/  # 阶段 9：评估 + 缓存 + 批量 + 全量 live 复评（✅ 0–7）
├── 10 强约束规则开发与幻觉抑制/  # 阶段 10：强约束提示 + 引用/格式校验 + 对抗评测（✅ 0–6）
├── 11 服务化与接口开发第一部分/  # 阶段 11：FastAPI + 同步/伪流式问答（✅ 已完成）
├── 12 服务化与接口开发第二部分/  # 阶段 12：会话/统计/文档 API + 文档索引（✅ 0–6 完成）
├── Med-RAG/                      # 产品打包交付：自包含 FastAPI + React Demo（✅）
├── （打包）LangChain_RAG/        # 打包规划与计划（final-schedule；02schedule 为资产编排草案）
├── （未来优化）打包后数据更新/    # 语料增补补丁 / 重建 runbook
└── 笔记/                     # 个人学习笔记
```

---

## 阶段一览

| 阶段 | 目录 | 状态 | 任务书 | 计划 | 运行入口（Jupyter） | 依赖 |
|------|------|------|--------|------|---------------------|------|
| **01** 验证模型 | [`01 验证模型/`](01%20验证模型/) | ✅ 已完成 | [`任务.txt`](01%20验证模型/任务.txt) | [`schedule.md`](01%20验证模型/schedule.md) | [`med-LLM-RAG.ipynb`](01%20验证模型/med-LLM-RAG.ipynb) | [`requirements.txt`](01%20验证模型/requirements.txt) |
| **02** 数据处理 | [`02 数据处理/`](02%20数据处理/) | ✅ 已完成 | [`任务.txt`](02%20数据处理/任务.txt) | [`schedule.md`](02%20数据处理/schedule.md) | [`partA.ipynb`](02%20数据处理/notebooks/med-data-EDA-partA.ipynb)（验证）· [`partB.ipynb`](02%20数据处理/notebooks/med-data-EDA-partB.ipynb)（全量） | [`requirements.txt`](02%20数据处理/requirements.txt) |
| **03** 文档解析与分割 | [`03 文档解析与分割/`](03%20文档解析与分割/) | ✅ 已完成 | [`任务.txt`](03%20文档解析与分割/任务.txt) | [`schedule.md`](03%20文档解析与分割/schedule.md) | [`doc-chunking.ipynb`](03%20文档解析与分割/notebooks/doc-chunking.ipynb)（验证）· [`full.ipynb`](03%20文档解析与分割/notebooks/doc-chunking-full.ipynb)（全量） | *复用 02* · [`requirements.txt`](03%20文档解析与分割/requirements.txt)（说明） |
| **04** 向量化与索引构建 | [`04 向量化与索引构建/`](04%20向量化与索引构建/) | ✅ **已完成** | [`任务.txt`](04%20向量化与索引构建/任务.txt) | [`schedule.md`](04%20向量化与索引构建/schedule.md) | [`vectorize-index.ipynb`](04%20向量化与索引构建/notebooks/vectorize-index.ipynb)（验证）· [`full.ipynb`](04%20向量化与索引构建/notebooks/vectorize-index-full.ipynb)（全量） | [`requirements.txt`](04%20向量化与索引构建/requirements.txt) |
| **05** 检索系统开发第一部分 | [`05 检索系统开发第一部分/`](05%20检索系统开发第一部分/) | ✅ **已完成** | [`任务.txt`](05%20检索系统开发第一部分/任务.txt) | [`schedule.md`](05%20检索系统开发第一部分/schedule.md) | [`query-enhancement.ipynb`](05%20检索系统开发第一部分/notebooks/query-enhancement.ipynb) | [`requirements.txt`](05%20检索系统开发第一部分/requirements.txt) |
| **06** 检索系统开发第二部分 | [`06 检索系统开发第二部分/`](06%20检索系统开发第二部分/) | ✅ **已完成** | [`任务.txt`](06%20检索系统开发第二部分/任务.txt) | [`schedule.md`](06%20检索系统开发第二部分/schedule.md) | [`retrieval-pipeline.ipynb`](06%20检索系统开发第二部分/notebooks/retrieval-pipeline.ipynb) | [`requirements.txt`](06%20检索系统开发第二部分/requirements.txt) |
| **07** 生成模块与提示词工程第一部分 | [`07 生成模块与提示词工程第一部分/`](07%20生成模块与提示词工程第一部分/) | ✅ **已完成** | [`任务.txt`](07%20生成模块与提示词工程第一部分/任务.txt) | [`schedule.md`](07%20生成模块与提示词工程第一部分/schedule.md) | [`generation-prompting.ipynb`](07%20生成模块与提示词工程第一部分/notebooks/generation-prompting.ipynb) | [`requirements.txt`](07%20生成模块与提示词工程第一部分/requirements.txt) |
| **08** 生成模块与提示词工程第二部分 | [`08 生成模块与提示词工程第二部分/`](08%20生成模块与提示词工程第二部分/) | ✅ **已完成** | [`任务.txt`](08%20生成模块与提示词工程第二部分/任务.txt) | [`schedule.md`](08%20生成模块与提示词工程第二部分/schedule.md) | [`medical-generation.ipynb`](08%20生成模块与提示词工程第二部分/notebooks/medical-generation.ipynb) | [`requirements.txt`](08%20生成模块与提示词工程第二部分/requirements.txt) |
| **09** 生成答案评估，缓存策略与批量处理 | [`09 生成答案评估，缓存策略与批量处理/`](09%20生成答案评估，缓存策略与批量处理/) | ✅ **已完成** | [`任务.txt`](09%20生成答案评估，缓存策略与批量处理/任务.txt) | [`schedule.md`](09%20生成答案评估，缓存策略与批量处理/schedule.md) | [`answer-eval-cache-batch.ipynb`](09%20生成答案评估，缓存策略与批量处理/notebooks/answer-eval-cache-batch.ipynb)（样本 0–6）· [`answer-eval-cache-batch-full.ipynb`](09%20生成答案评估，缓存策略与批量处理/notebooks/answer-eval-cache-batch-full.ipynb)（全量 7） | [`requirements.txt`](09%20生成答案评估，缓存策略与批量处理/requirements.txt) |
| **10** 强约束规则开发与幻觉抑制 | [`10 强约束规则开发与幻觉抑制/`](10%20强约束规则开发与幻觉抑制/) | ✅ **已完成** | [`任务.txt`](10%20强约束规则开发与幻觉抑制/任务.txt) | [`schedule.md`](10%20强约束规则开发与幻觉抑制/schedule.md) | [`constraint-hallucination.ipynb`](10%20强约束规则开发与幻觉抑制/notebooks/constraint-hallucination.ipynb)（C0–C6） | [`requirements.txt`](10%20强约束规则开发与幻觉抑制/requirements.txt) |
| **11** 服务化与接口开发第一部分 | [`11 服务化与接口开发第一部分/`](11%20服务化与接口开发第一部分/) | ✅ **已完成** | [`任务.txt`](11%20服务化与接口开发第一部分/任务.txt) | [`schedule.md`](11%20服务化与接口开发第一部分/schedule.md) · [`服务化接口报告.md`](11%20服务化与接口开发第一部分/docs/服务化接口报告.md) | [`api-smoke.ipynb`](11%20服务化与接口开发第一部分/notebooks/api-smoke.ipynb)（C0–C4.5） | [`requirements.txt`](11%20服务化与接口开发第一部分/requirements.txt) |
| **12** 服务化与接口开发第二部分 | [`12 服务化与接口开发第二部分/`](12%20服务化与接口开发第二部分/) | ✅ **0–6 完成** | [`任务.txt`](12%20服务化与接口开发第二部分/任务.txt) | [`schedule.md`](12%20服务化与接口开发第二部分/schedule.md) · [`部署说明`](12%20服务化与接口开发第二部分/docs/部署与API调用说明.md) · [`报告`](12%20服务化与接口开发第二部分/docs/服务化接口第二部分报告.md) | [`api-ops-smoke.ipynb`](12%20服务化与接口开发第二部分/notebooks/api-ops-smoke.ipynb)（C0–C4）· [`api-ops-full.ipynb`](12%20服务化与接口开发第二部分/notebooks/api-ops-full.ipynb)（F0+F1） | [`requirements.txt`](12%20服务化与接口开发第二部分/requirements.txt) |
| **打包 · Med-RAG** | [`Med-RAG/`](Med-RAG/) | ✅ **Demo 已落地** | [`（打包）任务.txt`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/%E4%BB%BB%E5%8A%A1.txt) | [`final-schedule.md`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/final-schedule.md) · [`Med-RAG/README`](Med-RAG/README.md) | API：`backend/scripts/run_api.py` · UI：`frontend`（`npm run dev`） | [`Med-RAG/requirements.txt`](Med-RAG/requirements.txt) |
| **打包 · 规划目录** | [`（打包）LangChain_RAG/`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/) | 📋 计划归档 | 同上 | [`final-schedule`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/final-schedule.md)（[`02schedule`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/02schedule.md) 资产草案 · [`01schedule`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/01schedule.md) 旧草案） | — | — |
| **未来优化·数据更新** | [`（未来优化）打包后数据更新/`](%EF%BC%88%E6%9C%AA%E6%9D%A5%E4%BC%98%E5%8C%96%EF%BC%89%E6%89%93%E5%8C%85%E5%90%8E%E6%95%B0%E6%8D%AE%E6%9B%B4%E6%96%B0/) | 📋 规划 | — | [`schedule.md`](%EF%BC%88%E6%9C%AA%E6%9D%A5%E4%BC%98%E5%8C%96%EF%BC%89%E6%89%93%E5%8C%85%E5%90%8E%E6%95%B0%E6%8D%AE%E6%9B%B4%E6%96%B0/schedule.md) | — | — |

**说明**

- 各阶段**具体要求与交付标准**以对应目录内 **`任务.txt`** 为准。
- 01–10 主入口多为 **Jupyter Notebook**；**11–12** 另提供 HTTP 服务：分阶段开发推荐 **`12 .../scripts/run_api.py`**（含 11 的 `/qa` + 12 会话/统计/文档）→ `/docs`。
- **产品演示 / 对外打包**：优先 [`Med-RAG/`](Med-RAG/)（自包含后端 + React UI）；计划与任务原文见 [`（打包）LangChain_RAG/`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/)。

---

## 各阶段完成总结

> 格式统一：**定位 → 任务 → 关键结果 → 产出索引**。实现细节、参数表、踩坑记录见各阶段 `schedule.md` 与 `docs/` 正式报告。

### 01 验证模型（2026-05-13）

- **定位**：工程起点；验证「本地 Ollama + PMC 样本文献 + 向量库 smoke test」是否可行。
- **主要任务**：拉取/解析 PMC XML 样本、本地 `deepseek-r1:7b` 推理、Chroma 最小检索实验。
- **关键结果**：本地 LLM 与样本文献链路跑通；为 02 全量数据处理提供环境与经验。
- **主要产出**：`med-LLM-RAG.ipynb`、`outputs/model_test_results.json`、验证期 XML 样本。
- **详情**：[`01 验证模型/schedule.md`](01%20验证模型/schedule.md)

### 02 数据处理（2026-05-27）

- **定位**：确定全库分割策略与 slim 语料；为 03 分割与 06 元数据回查提供基础数据。
- **主要任务**：验证期 97 篇 + 全量 4,557,627 篇 EDA；输出 `chunk_strategy_config.json`。
- **关键结果**：验证期与全量 P95 token、单块占比一致；策略 `chunk_size=400, overlap=80` **无需调整**。
- **主要产出**：`E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl`（8.9 GB）；[`docs/RAG数据分析与设计说明.md`](02%20数据处理/docs/RAG数据分析与设计说明.md)。
- **详情**：[`02 数据处理/schedule.md`](02%20数据处理/schedule.md)

### 03 文档解析与分割（2026-05-27）

- **定位**：将 slim 转为可检索 chunk；产出样本库（开发）与全量库（生产）。
- **主要任务**：按 02 策略全量分割；验证样本 1,000 篇 → 1,267 chunks。
- **关键结果**：全量 **6,107,296** chunks；token 超限 0；单块比例与验证期一致。
- **主要产出**：`E:\...\oa_comm_chunks.jsonl`；[`chunks_sample.jsonl`](03%20文档解析与分割/data/processed/chunks_sample.jsonl)；[`docs/文档分割处理报告.md`](03%20文档解析与分割/docs/文档分割处理报告.md)。
- **详情**：[`03 文档解析与分割/schedule.md`](03%20文档解析与分割/schedule.md)

### 04 向量化与索引构建（2026-06-03）

- **定位**：语义检索底座；BGE 嵌入 + Chroma 持久化索引。
- **主要任务**：样本 1,267 条验证 + 全量 610 万条建库（GPU）。
- **关键结果**：`pmc_oa_comm_full` 入库 6,107,296 条；384 维 cosine；C3–C5 检索与元数据过滤通过。
- **主要产出**：现迁入 [`Dataset/chroma/chroma_db_full/`](Dataset/)（~71 GB，**.gitignore**）；[`docs/向量化与索引报告.md`](04%20向量化与索引构建/docs/向量化与索引报告.md)；`embedder.py` / `index_builder.py`。
- **详情**：[`04 向量化与索引构建/schedule.md`](04%20向量化与索引构建/schedule.md)

### 05 检索系统开发第一部分（2026-06-10）

- **定位**：查询理解层；把自然语言 query 结构化为向量/BM25 查询与 filters。
- **主要任务**：`MedicalQueryEnhancer`、同义词表、双库 smoke（样本 vs 全量 Chroma）。
- **关键结果**：样本库 query ~12 ms、全量 ~16 ms；05→04 检索路径打通。
- **主要产出**：`query_enhancer.py`、`medical_synonyms.json`；[`docs/查询理解与增强报告.md`](05%20检索系统开发第一部分/docs/查询理解与增强报告.md)。
- **详情**：[`05 检索系统开发第一部分/schedule.md`](05%20检索系统开发第一部分/schedule.md)

### 06 检索系统开发第二部分（2026-06-18；09 联动 2026-07-08）

- **定位**：检索执行层；向量 + BM25 → RRF 融合 → cross-encoder 重排。
- **主要任务**：`RetrievalPipeline` 端到端；样本库 5 query 评测 + C12 可选全量联调；**09 阶段 7** 扩展分片 BM25 离线索引。
- **关键结果**：样本库 5/5 链路通；全量 metformin query 命中真实 RCT（`PMC2566605`）。**09 联动**：`bm25_sharded.py` + `Dataset/bm25/bm25_full`（62 片 · 610 万）供 `from_mode("full")` 自动加载。
- **主要产出**：`pipeline.py`、`pipeline_eval.json`；[`docs/检索流水线报告.md`](06%20检索系统开发第二部分/docs/检索流水线报告.md)。
- **详情**：[`06 检索系统开发第二部分/schedule.md`](06%20检索系统开发第二部分/schedule.md) §「验证范围说明」「09 阶段联动扩展」

### 07 生成模块与提示词工程第一部分（2026-06-24）

- **定位**：生成准备层；把 06 `reranked` 整理为 LLM 可用的 `context_text` 与四阶段 Prompt。
- **主要任务**：`ContextAssembler`（去重/多样化/控长）+ `PromptStage` 模板；**本阶段不调用 LLM**。
- **关键结果**：pytest **16 passed**；notebook C0–C7 样例 JSON 导出。
- **主要产出**：`context_assembler.py`、`prompts.py`；[`docs/上下文组装与提示工程报告.md`](07%20生成模块与提示词工程第一部分/docs/上下文组装与提示工程报告.md)。
- **详情**：[`07 生成模块与提示词工程第一部分/schedule.md`](07%20生成模块与提示词工程第一部分/schedule.md)

### 08 生成模块与提示词工程第二部分（2026-07-02）

- **定位**：生成执行层；Ollama 多步生成 + 后处理，串联 05→06→07 产出 `answer` + `sources`。
- **主要任务**：`LLMGenerator`、`MedicalGenerationPipeline`、引用后处理；批量评测 `generation_eval.json`。
- **关键结果**：pytest **17 passed**；4 条基准 query 快照（基于 **06 样本库** `pipeline_eval.json` + 本机 Ollama）。
- **主要产出**：`generation_pipeline.py`、`run_generation_eval.py`；[`docs/医学生成流水线报告.md`](08%20生成模块与提示词工程第二部分/docs/医学生成流水线报告.md)。
- **详情**：[`08 生成模块与提示词工程第二部分/schedule.md`](08%20生成模块与提示词工程第二部分/schedule.md)

### 09 生成答案评估，缓存策略与批量处理（2026-07-08）

- **定位**：质量与工程优化横切层；在 08 外侧做评估、缓存、批量调度，不改变 08 生成内核。
- **主要任务**：阶段 0–6 样本库验证（`AnswerEvaluator` / `GenerationCache` / `BatchRunner` / `PipelineWithEval`）；**阶段 7** 全量 live 复评 + 分片 BM25 离线索引。
- **关键结果**：
  - 样本 offline：pytest **18 passed**；缓存二轮命中率 **1.0**；rouge1_avg=0.0768、key_info_recall_avg=0.2321。
  - **全量 live**（610 万检索 + Ollama）：4/4 跑通；recall_avg **0.2738**（+0.042 vs 样本）；分片 BM25 同语料 top-10 重叠 **0.95**。
- **主要产出**：
  - 样本：`eval_cache_batch_report.json`、`answer-eval-cache-batch.ipynb`
  - 全量：`eval_cache_batch_report_full.json`、`Dataset/bm25/bm25_full/`、`answer-eval-cache-batch-full.ipynb`、`full_eval.py`
  - 报告：[`docs/答案评估与缓存报告.md`](09%20生成答案评估，缓存策略与批量处理/docs/答案评估与缓存报告.md)（§4 样本 · §6 全量）
- **详情**：[`09 .../schedule.md`](09%20生成答案评估，缓存策略与批量处理/schedule.md) 阶段 0–7

### 10 强约束规则开发与幻觉抑制（✅ 2026-07-15 完成）

- **定位**：安全约束与幻觉抑制层；在 08 生成链路上叠加硬纪律（拒答 / 合法引用 / 禁编造 / 格式），生成后校验并可重试；用对抗用例验收。
- **主要任务**：`ConstraintPromptBundle`、`CitationGuard`、`FormatChecker`、`ConstrainedGenerationPipeline`、对抗评测与指标报告。
- **关键设计**：默认全量路径就绪（`from_mode("full")`）；陷阱用 fixture；格式别名兼容 08；`boundary_hit` 豁免三节；journal/year 默认 relaxed；约束 **`append_to`** 不替换 07 system。
- **关键结果（fixture / mock 实测）**：
  - pytest **43 passed**；C0.5 全量资源 `ready=true`，Ollama `deepseek-r1:7b` 可用
  - C4 fixture：`citation.ok` / `format.ok`，`retry_count=0`，格式分 `0.85`（journal/year 仅 warn）
  - C5/C6 mock：硬幻觉率 **0.0**（0/3）、拒答命中率 **1.0**、引用/格式/术语合规率均为 **1.0**
  - > mock 验证计分与粘合链路；真模型 live 须另行评测
- **主要产出**：
  - 代码：`src/constraint_prompts.py` / `citation_guard.py` / `format_checker.py` / `constrained_pipeline.py` / `adversarial_eval.py`
  - 数据：`medical_abbrev.json`、`adversarial_cases.json`
  - notebook：[`constraint-hallucination.ipynb`](10%20强约束规则开发与幻觉抑制/notebooks/constraint-hallucination.ipynb)（规则/mock）；[`constraint-mvp-observe.ipynb`](10%20强约束规则开发与幻觉抑制/notebooks/constraint-mvp-observe.ipynb)（真模型完整答案 MVP）
  - CLI：`scripts/run_adversarial_eval.py`；报告：`outputs/samples/adversarial_eval_report_full.json`
  - 报告：[`docs/强约束与幻觉抑制报告.md`](10%20强约束规则开发与幻觉抑制/docs/强约束与幻觉抑制报告.md)
- **详情**：[`10 .../schedule.md`](10%20强约束规则开发与幻觉抑制/schedule.md) 阶段 0–6

### 11 服务化与接口开发第一部分（✅ 2026-07-25 完成）

- **定位**：RAG **服务接入层**——把 10 约束流水线封成可对外调用的 HTTP API（非产品前端；`/` 返回 JSON）。
- **主要任务**：FastAPI 骨架（`ResponseModel` / 错误码 / 全局异常 / 日志 / `/health`·`/ready`）；同步 `POST /api/v1/qa` + 伪流式 `POST /api/v1/qa/stream`；内存会话 + 调用 JSONL；集成 10 `ConstrainedGenerationPipeline`。
- **关键设计**：开发默认 `retrieval_mode=sample`；流式 MVP = **`stream_mode=pseudo`**（非整段 Ollama token 真流）；校验失败统一 **HTTP 400 + code=1001**；全量连通抽检见阶段 4.5。
- **关键结果**：
  - pytest **41 passed**；notebook C0–C4.5
  - full + Ollama 最新抽检：sync ≈ **180 s**，citation/format ok，sources 为全量 PMC id
  - 热身后 HTTP `POST /qa` → 200 / `code=0`
- **主要产出**：
  - 代码：`app/`（api · core · schemas · services）· `scripts/run_api.py` · `scripts/run_full_api_smoke.py`
  - notebook：[`api-smoke.ipynb`](11%20服务化与接口开发第一部分/notebooks/api-smoke.ipynb)
  - 抽检：`outputs/reports/full_api_smoke*`（JSON / PNG）
  - 报告：[`docs/服务化接口报告.md`](11%20服务化与接口开发第一部分/docs/服务化接口报告.md)（含前端接入契约 §3）
- **详情**：[`11 .../schedule.md`](11%20服务化与接口开发第一部分/schedule.md) 阶段 0–5

### 12 服务化与接口开发第二部分（✅ 0–6 完成 · 2026-07-29）

- **定位**：在 11 之上补 **运营层 API**（会话 CRUD / 统计 / 文档菜单册），并建设篇级 `documents` 索引；与 `/qa` **共用** SessionStore 与 `qa_calls.jsonl`。
- **主要任务**：
  - 阶段 0：骨架 + `bridge11`；`documents/sample`（1000）与 `documents/full`（4,557,627）索引
  - 阶段 1：`POST/GET/DELETE /sessions`；完整 `turns`；无效 → **3002**（≠ QA 自动新建）
  - 阶段 2：`/stats/qa|index|health`（chunk ≠ document；`database=skipped`）
  - 阶段 3：`/documents` 分页与按 pmcid；缺失 → **3001**；收紧通用 404→1001
  - 阶段 4：集成测试 · Postman · OpenAPI · 部署文档 · smoke C4
  - 阶段 5：全量仿真 `run_full_ops_smoke`（sessions/stats/documents + live full QA）
  - 阶段 6：交付报告 · `outputs/samples/` · README 对齐
- **关键设计**：`wire_stage11` 挂载 11 health/qa；Depends 双端 override 防 Store 分裂；`doc_id`=`pmcid`；Windows live QA 主线程（对齐 11）。
- **关键结果**：pytest **18 passed**（sample）；smoke **C0–C4**；full live **ok**（qa1≈181s / qa2≈225s；documents get `PMC6213955`；`chunk_count=6,107,296`）；`stage=12-6`。
- **主要产出**：
  - 代码：`app/api/{sessions,stats,documents}.py` · `services/` · `bridge11.py` · `full_ops_smoke.py`
  - 部署：[`docs/部署与API调用说明.md`](12%20服务化与接口开发第二部分/docs/部署与API调用说明.md) · [`.env.example`](12%20服务化与接口开发第二部分/.env.example) · [`postman/MedRAG_API.postman_collection.json`](12%20服务化与接口开发第二部分/postman/MedRAG_API.postman_collection.json)
  - 报告：[`docs/服务化接口第二部分报告.md`](12%20服务化与接口开发第二部分/docs/服务化接口第二部分报告.md)
  - notebook：[`api-ops-smoke.ipynb`](12%20服务化与接口开发第二部分/notebooks/api-ops-smoke.ipynb) · [`api-ops-full.ipynb`](12%20服务化与接口开发第二部分/notebooks/api-ops-full.ipynb)（F0+F1）
  - 全量报告：`outputs/reports/full_ops_smoke.json` · `full_ops_smoke_*.png` · [`outputs/samples/`](12%20服务化与接口开发第二部分/outputs/samples/)
- **详情**：[`12 .../schedule.md`](12%20服务化与接口开发第二部分/schedule.md)

### 打包 · Med-RAG（✅ Demo 已落地 · 2026-08）

- **定位**：把 01–12 已验证能力收成**可独立运行**的产品 Demo 目录（不依赖兄弟阶段路径）；含 FastAPI（问答/会话/统计/文档/上传）+ React 双栏聊天 UI。
- **主要任务**：代码自包含迁移；`data/chat` 会话落盘；CORS；sample 空库/回形针 ingest；Markdown 渲染与文档站内查看；部署 / 代码 / 数据导入说明；zip 发布脚本。
- **关键结果**：默认 `MED_RAG_RETRIEVAL_MODE=sample` 可问答；切换 full 仅需迁入资产 + 改 `.env` + 重启（一期上传固定写 sample，不更新全库）。
- **主要产出**：
  - 包入口：[`Med-RAG/README.md`](Med-RAG/README.md)
  - 文档：[`部署`](Med-RAG/docs/%E9%83%A8%E7%BD%B2%E6%96%87%E6%A1%A3.md) · [`代码说明`](Med-RAG/docs/%E4%BB%A3%E7%A0%81%E8%AF%B4%E6%98%8E%E6%96%87%E6%A1%A3.md) · [`数据存储与导入`](Med-RAG/docs/%E6%95%B0%E6%8D%AE%E5%AD%98%E5%82%A8%E4%B8%8E%E5%AF%BC%E5%85%A5%E5%8F%82%E8%80%83.md) · [`流程图`](Med-RAG/docs/%E6%B5%81%E7%A8%8B%E5%9B%BE.md)
  - 计划：[`final-schedule.md`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/final-schedule.md)
  - 大数据共享：[Google Drive Dataset](https://drive.google.com/drive/folders/1uK-2nbpOAWH61pWWrArpR8fdUzUihZ7H?usp=sharing)（上传可能仍在进行）
- **详情**：[`Med-RAG/docs/`](Med-RAG/docs/) · Dataset [`README`](Dataset/README.md) / [`打包资产清单`](Dataset/打包资产清单.md)

---

## Python 环境与依赖

### 推荐环境

| 项 | 值 |
|----|-----|
| Conda 环境名 | `med-rag-verify`（01–12 共用） |
| Python | 3.11.x |
| 平台 | Windows / macOS |

### 一键安装（推荐）

```powershell
# Windows：创建环境 + 01/02 基础依赖
.\setup_windows_env.ps1

# 安装 01→12 全部 Python 依赖（含 04–12；03 无新增可跳过）
.\install_all_requirements.ps1

# 或仅补装阶段 12（若 01–11 已齐）：
# pip install -r "12 服务化与接口开发第二部分/requirements.txt"
```

根目录 [`requirements.txt`](requirements.txt) 记录安装顺序；因目录名含空格，请用 [`install_all_requirements.ps1`](install_all_requirements.ps1) 而非 `pip install -r requirements.txt`。

### 分阶段新增依赖一览

| 阶段 | `requirements.txt` | 相对上一阶段新增 / 说明 |
|------|-------------------|-------------------------|
| 01 | [`01 .../requirements.txt`](01%20验证模型/requirements.txt) | Jupyter、pandas、datasets、lxml、chromadb、LangChain、torch（CPU 默认）等全量锁定 |
| 02 | [`02 .../requirements.txt`](02%20数据处理/requirements.txt) | matplotlib、seaborn、sentence-transformers 等 |
| 03 | [`03 .../requirements.txt`](03%20文档解析与分割/requirements.txt) | **无新增**（文档说明；复用 02：langchain-text-splitters 等） |
| 04 | [`04 .../requirements.txt`](04%20向量化与索引构建/requirements.txt) | chromadb、BGE 相关（复用 02 的 sentence-transformers；`embedder.py` 直载 transformers） |
| 05 | [`05 .../requirements.txt`](05%20检索系统开发第一部分/requirements.txt) | 查询增强相关（基本复用 04） |
| 06 | [`06 .../requirements.txt`](06%20检索系统开发第二部分/requirements.txt) | **`rank-bm25`** |
| 07 | [`07 .../requirements.txt`](07%20生成模块与提示词工程第一部分/requirements.txt) | **无强制新增**（可选 gpt2 tokenizer） |
| 08 | [`08 .../requirements.txt`](08%20生成模块与提示词工程第二部分/requirements.txt) | **`httpx`**（Ollama HTTP） |
| 09 | [`09 .../requirements.txt`](09%20生成答案评估，缓存策略与批量处理/requirements.txt) | **`rouge-score`**、`pytest`（httpx 与 08 重叠） |
| 10 | [`10 .../requirements.txt`](10%20强约束规则开发与幻觉抑制/requirements.txt) | **无强制新包**；清单复列 `pytest`、`httpx`（与 08/09 重叠，便于缺包时补装） |
| 11 | [`11 .../requirements.txt`](11%20服务化与接口开发第一部分/requirements.txt) | 新增 **`fastapi`**、**`uvicorn[standard]`**（另列 pydantic/httpx/pytest） |
| 12 | [`12 .../requirements.txt`](12%20服务化与接口开发第二部分/requirements.txt) | 新增 **`python-dotenv`**；复列 fastapi/uvicorn/pydantic/httpx/pytest（文档索引用标准库 `sqlite3`） |

### 04 全量 GPU 补充（可选）

> 01 默认 PyPI 的 torch 常为 **CPU 版**。01–03 不依赖 GPU；**04 全量 610 万嵌入**前需 CUDA 版 torch。

```powershell
.\setup_stage04_gpu.ps1
# 或：pip uninstall torch -y && pip install torch --index-url https://download.pytorch.org/whl/cu124
```

验证：`torch.cuda.is_available()` 为 `True`。勿在 GPU 配置后用 `pip install -r 01.../requirements.txt` 覆盖回 CPU 版。详见原 04 notebook 踩坑：`笔记/04笔记.md` Q12。

---

## 本地部署指南

> 从 GitHub 克隆后的搭建顺序：**环境 → 大文件/模型 → 按阶段 notebook 或 CLI 运行**。

### 1. 克隆与 Python 环境

```powershell
git clone <repo-url> "D:\谷歌"
cd "D:\谷歌"
.\setup_windows_env.ps1
.\install_all_requirements.ps1
```

### 2. `.gitignore` 与未上传内容

以下**不会**随仓库提供，需在本地准备或运行后生成：

| 类型 | 路径 / 模式 | 说明 | 获取方式 |
|------|-------------|------|----------|
| 缓存 | `**/caches/`、`__pycache__/`、`.ipynb_checkpoints/` | HF/datasets 缓存、运行时生成 | 首次运行自动创建 |
| 密钥 | `.env`、`secrets/` | 勿提交 | 本地自建（若需要） |
| Ollama 模型 | `**/ollama_models/`、`deepseek-r1:7b` | 01/08 LLM | `ollama pull deepseek-r1:7b` |
| **统一 Dataset** | [`Dataset/`](Dataset/)（整目录 ignore，保留 README / 清单 / documents 说明） | Chroma / BM25 / chunks / slim / **documents sqlite** **现行主路径** | 见下节；清理对照 [`缓存记录.md`](缓存记录.md) |
| 验证期向量库 | `Dataset/chroma/chroma_db/` | 样本库（旧 `04/.../chroma_db` 已联接） | 可 notebook 重建 |
| **全量向量库** | `Dataset/chroma/chroma_db_full/`（~71 GB） | 生产检索 | 自 04 迁入；E: 可作备份 |
| **slim JSONL** | `Dataset/processed/oa_comm_slim.jsonl`（~8.9 GB） | 元数据回查 / 建 documents | 自 06 迁入 |
| **全量 chunks** | `Dataset/processed/oa_comm_chunks.jsonl`（~9.1 GB） | BM25 语料 | 自 09 迁入 |
| **全量 BM25 索引** | `Dataset/bm25/bm25_full/` | 分片离线索引（62 片） | 自 09 迁入；构建脚本默认写入此处 |
| **篇级文档索引** | `Dataset/documents/{sample,full}/*.sqlite` | 12 `/documents`；full ~11.5 GB | 12 `build_documents_index.py`；**不进 Git** |
| 运行日志 | `**/outputs/logs/*.log`、`qa_calls.jsonl` | API / QA 调用流水 | 本地运行生成；仓库仅保留 `.gitkeep` |
| PMC 原始压缩包 | 外接盘 ~100 GB+ | 02 全量解析 | 按 02 notebook partB 说明 |

**已随仓库提供（可直接用）**：01 验证 XML、02/03 样本 JSONL、04 样本 chunks 与统计 JSON、05–09 代码与样例输出 JSON 等（见下表）。

| 数据 | 位置 | 说明 |
|------|------|------|
| 01 验证期 XML | `01 验证模型/data/raw/extracted/` | 284 篇 |
| 02 验证样本 | `02 数据处理/data/processed/sample*.jsonl` | 100→97 篇清洗后 |
| 03 验证 chunks | `03 .../data/processed/chunks_sample.jsonl` | **1,267**（开发默认语料） |
| 04 验证 chunks | `04 .../data/processed/chunks_sample.jsonl` | 复制自 03 |
| 04 全量统计 JSON | `04 .../outputs/tables/index_stats.json` 等 | 建库验证报告（库本体在本地 D:/E:） |

### 3. Ollama（阶段 01 / 08）

```bash
cd "01 验证模型"
export OLLAMA_MODELS="$(pwd)/ollama_models"   # Windows 见 notebook 说明
ollama pull deepseek-r1:7b
```

确保 `http://127.0.0.1:11434` 可访问后再跑 08/09 `--mode live`，以及 11 的 live / full 抽检。

### 4. 按阶段运行

1. **File → Open Folder** → 选择对应阶段目录  
2. Jupyter 内核：**`med-rag-verify`**  
3. 按 notebook 章节顺序执行（04 全量：`vectorize-index-full.ipynb` C0→C5）  
4. CLI / API 示例见「各阶段交付物速查」  
5. **阶段 11（HTTP 底座）**：`cd "11 服务化与接口开发第一部分"` → `python scripts/run_api.py` → `http://127.0.0.1:8000/docs`  
6. **阶段 12（分阶段日常 API）**：内核 **`med-rag-verify`**；`copy .env.example .env` → `cd "12 服务化与接口开发第二部分"` → `python scripts/run_api.py --no-reload` → `/docs`（含 sessions/stats/documents + 11 的 `/qa`）；冒烟 [`api-ops-smoke.ipynb`](12%20服务化与接口开发第二部分/notebooks/api-ops-smoke.ipynb) C0–C4；文档索引见 [`Dataset/documents/`](Dataset/documents/README.md)；部署说明见 [`12 .../docs/部署与API调用说明.md`](12%20服务化与接口开发第二部分/docs/部署与API调用说明.md)
7. **产品 Demo（Med-RAG，推荐演示入口）**：见下节；详 [`Med-RAG/README.md`](Med-RAG/README.md) · [`Med-RAG/docs/部署文档.md`](Med-RAG/docs/%E9%83%A8%E7%BD%B2%E6%96%87%E6%A1%A3.md)

### 4.1 产品 Demo：Med-RAG（自包含）

不依赖兄弟阶段路径；运行时只用 `Med-RAG/data/`。

```powershell
conda activate med-rag-verify
cd Med-RAG
pip install -r requirements.txt
copy .env.example .env
python backend/scripts/run_api.py --no-reload   # http://127.0.0.1:8000/docs

# 另开终端
cd Med-RAG\frontend
npm install
npm run dev                                     # http://127.0.0.1:5173
```

| 模式 | 说明 |
|------|------|
| `sample`（默认） | 可空启动；回形针上传固定写入 sample 索引 |
| `full` | 迁入全量资产后改 `.env` 的 `MED_RAG_RETRIEVAL_MODE=full` 并重启；一期 Demo **不能**用上传更新全库 |

大数据可从本地 [`Dataset/`](Dataset/) 或 [Google Drive 共享](https://drive.google.com/drive/folders/1uK-2nbpOAWH61pWWrArpR8fdUzUihZ7H?usp=sharing) 迁入 `Med-RAG/data/`（步骤见 [`数据存储与导入参考`](Med-RAG/docs/%E6%95%B0%E6%8D%AE%E5%AD%98%E5%82%A8%E4%B8%8E%E5%AF%BC%E5%85%A5%E5%8F%82%E8%80%83.md)）。

### 5. 统一 Dataset（新代码默认读取这里）

大数据已迁入 [`Dataset/`](Dataset/)（说明见 [`Dataset/README.md`](Dataset/README.md)）。**新项目 / 新脚本请直接使用根目录 [`dataset_paths.py`](dataset_paths.py)**，不要再写死各阶段 `data/`：

```python
from dataset_paths import (
    DATASET_ROOT,
    CHROMA_FULL_DIR,
    CHROMA_SAMPLE_DIR,
    CHUNKS_FULL_JSONL,
    SLIM_JSONL,
    BM25_FULL_DIR,
)
```

既有 06–10 代码经 `06/src/config.py` 的 `resolve_*`：**优先 Dataset** → 旧阶段路径 / 硬链接·联接 → `E:\med-llm-rag-datasets`。

| 资源 | Dataset 路径 | collection / 说明 |
|------|--------------|-------------------|
| 全量 Chroma | `Dataset/chroma/chroma_db_full/` | `pmc_oa_comm_full` |
| 样本 Chroma | `Dataset/chroma/chroma_db/` | `pmc_oa_comm_sample` |
| chunks | `Dataset/processed/oa_comm_chunks.jsonl` | BM25 语料 |
| slim | `Dataset/processed/oa_comm_slim.jsonl` | 年份/期刊回查 |
| BM25 | `Dataset/bm25/bm25_full/` | `bm25_sharded_v1` · 62 片 |
| 篇级文档 | `Dataset/documents/sample|full/` | sqlite · 12 `/documents`（sample 1000 / full 455 万） |

可选环境变量：`MED_RAG_DATASET_ROOT`（覆盖 Dataset 根）、`STAGE09_BM25_FULL_DIR`（仅 BM25）。

> **说明**：若某次 live 运行仍占用 `chroma.sqlite3`，全量 Chroma 可能暂时以「Dataset → 04 legacy」目录联接存在；关闭 Jupyter/Python 后执行  
> `powershell -File scripts/materialize_chroma_to_dataset.ps1` 即可改为实体目录（legacy 再联接回 Dataset）。详见 [`缓存记录.md`](缓存记录.md)。

### 6. 生产 RAG 运行提醒

开发阶段 06–09 **样本验证**默认 **样本库（1,267 chunks）**；**全量生产**（09 阶段 7 已打通）。**阶段 10 默认直接全量**（`from_mode("full")`）：

- 数据：上表 Dataset 路径（`resolve_*("full")`）
- 代码：`RetrievalPipeline.from_mode("full")`
- 全量 live 评估：`run_eval_cache_batch.py --mode live --retrieval-mode full`
- **10 约束流水线**：同上；对抗陷阱用 `fixture_chunks`；CLI `run_adversarial_eval.py --mock` / live，详见 [`10/schedule.md`](10%20强约束规则开发与幻觉抑制/schedule.md)

---

## 各阶段交付物速查

> 面向**后续开发**：路径、⚠️ 边界、可调用接口、**schedule 实现注意事项**（精炼）。完整踩坑见各阶段 `schedule.md`。

### 01 验证模型（✅）

- **产出**：`outputs/model_test_results.json`；`data/processed/sample.jsonl`
- **入口**：`med-LLM-RAG.ipynb`
- **接口**：Ollama 本地服务 + Chroma smoke（见 notebook §6）
- **后续开发注意**（[`schedule.md`](01%20验证模型/schedule.md)「关键发现」）：
  - Ollama **`think=False`**，否则 deepseek-r1 思考链占满 token、易超时（08+ 沿用）。
  - 纯 LLM 无文献时医学准确性不足——RAG 价值实证。
- **详情**：[`schedule.md`](01%20验证模型/schedule.md)

### 02 数据处理（✅）

- **产出**：[`docs/RAG数据分析与设计说明.md`](02%20数据处理/docs/RAG数据分析与设计说明.md)；`outputs/tables/chunk_strategy_config.json`
- **全量数据**：`E:\med-llm-rag-datasets\processed\oa_comm_slim.jsonl`（**不在 Git**）
- **接口**：`src/parse_pmc.py`、`build_jsonl.py`、`full_scale_pipeline.py`
- **后续开发注意**（[`schedule.md`](02%20数据处理/schedule.md)）：
  - 本阶段不做向量入库与 LLM；slim 为 03 分割与 06 元数据回查上游。
  - 策略 `chunk_size=400, overlap=80` 已全量验证，报告 §8 含数据侧 RAG 建议。
- **详情**：[`schedule.md`](02%20数据处理/schedule.md)

### 03 文档解析与分割（✅）

- **产出**：[`docs/文档分割处理报告.md`](03%20文档解析与分割/docs/文档分割处理报告.md)；[`chunks_sample.jsonl`](03%20文档解析与分割/data/processed/chunks_sample.jsonl)（1,267）
- **全量**：`E:\...\oa_comm_chunks.jsonl`（6,107,296，**不在 Git**）
- **接口**：`src/chunker.py`
- **后续开发注意**（[`03/04 schedule.md`](03%20文档解析与分割/schedule.md)）：
  - 样本为前 1,000 篇完整文献，供 04–09 开发；**生产 BM25 须全量 chunks**。
  - chunk metadata **无 pub_year**（年份在 06 检索后回查 slim）。
- **详情**：[`schedule.md`](03%20文档解析与分割/schedule.md)

### 04 向量化与索引构建（✅）

- **产出**：[`docs/向量化与索引报告.md`](04%20向量化与索引构建/docs/向量化与索引报告.md)；`src/embedder.py`、`index_builder.py`
- **全量库**：`Dataset/chroma/chroma_db_full/` · `pmc_oa_comm_full`（**不在 Git**，~71 GB）
- **接口**：`encode_queries()` / `encode_documents()`；`ChromaIndexBuilder.query()`
- **后续开发注意**（[`schedule.md`](04%20向量化与索引构建/schedule.md) §「**实现注意事项**」）：
  - **建库不加指令、查询必须加** BGE 前缀；漏加静默降准确率，查询用 `encode_queries()`。
  - 建库与查询同一模型 `bge-small-en-v1.5`（384 维），见 `index_stats.json`。
  - **勿用** `chroma_db/`、`chroma_repair_test/`（半成品）；RAG 用 **`chroma_db_full`**。
  - 全量前需 CUDA torch；Jupyter 避免 `sentence_transformers` 崩内核（已改 transformers 直载）。
- **详情**：[`schedule.md`](04%20向量化与索引构建/schedule.md) §「实现注意事项」「阶段收尾」

### 05 检索系统开发第一部分（✅）

- **产出**：`MedicalQueryEnhancer` → `EnhancedQuery`；[`docs/查询理解与增强报告.md`](05%20检索系统开发第一部分/docs/查询理解与增强报告.md)
- **样例**：`outputs/samples/enhancement_examples.json`
- **接口**：`query_enhancer.enhance(query)` → `vector_query` / `keyword_query` / `filters`
- **后续开发注意**（[`schedule.md`](05%20检索系统开发第一部分/schedule.md) §「**已知约束**」）：
  - BGE 查询 instruction **须与 04 一致**，勿自改措辞。
  - `filters` 可解析年份，但 Chroma **无 pub_year metadata**（06 后过滤补偿）。
  - 静态同义词 JSON；开发联调用样本库 1,267 条。
- **详情**：[`schedule.md`](05%20检索系统开发第一部分/schedule.md)

### 06 检索系统开发第二部分（✅）

> **验证范围**：日常 notebook/CLI 默认 **样本库（1,267 chunks）**；`from_mode("full")` + `Dataset/bm25/bm25_full` 用于全量生产（09 阶段 7 已构建分片索引）。

| 用途 | 开发（sample） | 生产（full） |
|------|----------------|--------------|
| 向量 | `Dataset/chroma/chroma_db` · `pmc_oa_comm_sample` | `Dataset/chroma/chroma_db_full` · `pmc_oa_comm_full` |
| BM25 语料 | `03 .../chunks_sample.jsonl` | **`Dataset/processed/oa_comm_chunks.jsonl`** |
| BM25 索引 | 现场 `build()` | **`Dataset/bm25/bm25_full/`**（分片离线索引） |
| 代码 | `RetrievalPipeline.from_mode("sample")` | **`from_mode("full")`** |

- **产出**：[`docs/检索流水线报告.md`](06%20检索系统开发第二部分/docs/检索流水线报告.md)；`pipeline_eval.json` · `pipeline_eval_full.json`
- **接口**：`RetrievalPipeline.run(query)` → `reranked`；`config.resolve_chroma()` / `resolve_chunks_path()` / `resolve_bm25_cache_dir()`
- **09 联动**（[`schedule.md`](06%20检索系统开发第二部分/schedule.md)「09 阶段联动扩展」）：`bm25_sharded.py`、`ShardedBM25Index`；`MultiPathRetriever.from_mode("full")` 优先加载分片缓存
- **后续开发注意**：
  - 融合默认 **`rrf`**；recency/authority 靠 slim 回查。
  - 分片 BM25 查询逐片加载，比单体慢；可预热/常驻优化。
- **详情**：[`schedule.md`](06%20检索系统开发第二部分/schedule.md)

```python
from pipeline import RetrievalPipeline
result = RetrievalPipeline.from_mode("sample").run("metformin cardiovascular effects")
top_chunks = result["reranked"]
```

### 07 生成模块与提示词工程第一部分（✅）

- **范围**：组装 + Prompt；**不调用 LLM**
- **契约**：[`输入候选格式约定.md`](07%20生成模块与提示词工程第一部分/输入候选格式约定.md)
- **接口**：`ContextAssembler.assemble(reranked, ...)` → `context_text`；`PROMPT_STAGES` / `render_prompt_stage(...)`
- **后续开发注意**（[`schedule.md`](07%20生成模块与提示词工程第一部分/schedule.md) §「风险与应对」）：
  - 输入首选 06 `reranked`；token 估算与 Ollama 实际 tokenizer 可能偏差。
  - 去重 Jaccard 0.85、同源降权可调；截断在句号边界。
- **详情**：[`schedule.md`](07%20生成模块与提示词工程第一部分/schedule.md)

### 08 生成模块与提示词工程第二部分（✅）

> **⚠️ 验证范围**：`generation_eval.json`（`offline_sample_pipeline_eval`）基于 **06 样本库** + Ollama。

- **产出**：[`docs/医学生成流水线报告.md`](08%20生成模块与提示词工程第二部分/docs/医学生成流水线报告.md)；`outputs/samples/generation_eval.json`
- **接口**：`MedicalGenerationPipeline.run(query)` → `answer` / `sources` / `generation_metrics`
- **CLI**：`scripts/run_generation_eval.py`（读 06 `pipeline_eval.json`）
- **后续开发注意**（[`schedule.md`](08%20生成模块与提示词工程第二部分/schedule.md)）：
  - **`think=False`**、`max_tokens`≥512；JSON 用 `extract_json`/`repair_json`。
  - 证据评估解析失败**不删 chunk**；调试可 `skip_critical_review=True`。
  - 全量切换：06 `from_mode("full")` 后重跑 `run_generation_eval.py` → 供 09 新快照。
- **详情**：[`schedule.md`](08%20生成模块与提示词工程第二部分/schedule.md)

### 09 生成答案评估，缓存策略与批量处理（✅ 0–7）

| 验证 | 语料 / 模式 | 入口 | 报告 |
|------|-------------|------|------|
| 样本 0–6 | 1,267 chunks · offline/live(sample) | `answer-eval-cache-batch.ipynb` | `eval_cache_batch_report.json` · 报告 §4 |
| **全量 7** | **610 万 · live(full)** | `answer-eval-cache-batch-full.ipynb` 或 CLI | `eval_cache_batch_report_full.json` · 报告 §6 |

- **产出**：[`docs/答案评估与缓存报告.md`](09%20生成答案评估，缓存策略与批量处理/docs/答案评估与缓存报告.md)；`ground_truth.json`；`eval_sample_vs_full.json`；`bm25_sharded_vs_mono_overlap.json`
- **接口**：`PipelineWithEval.run_with_cache_and_eval(...)` → `generation` / `evaluation` / `cache`；`full_eval.build_pipeline_with_eval_live_full()`（全量 live）
- **预留接口（供 11+ 复用 / 借鉴，本阶段未全部接线）**：

  | 预留 | 路径 | 用途 | 现状 |
  |------|------|------|------|
  | `ModelAdapter` / `GenerationRequest` / `GenerationResponse` | [`src/model_adapter.py`](09%20生成答案评估，缓存策略与批量处理/src/model_adapter.py) | 多模型统一 `generate(request)`；`PipelineModelAdapter` 包装 `pipeline.run` | ✅ 已实现轻量适配；批量主路径仍可直接 callable |
  | `SnapshotModelAdapter` | 同上 | offline 用 08 `generation_eval` 快照冒充生成 | ✅ 可用 |
  | `BaseCacheBackend` / `MemoryCacheBackend` | [`src/generation_cache.py`](09%20生成答案评估，缓存策略与批量处理/src/generation_cache.py) | 答案缓存后端；未来 sqlite/redis | 接口已留；**持久化未接入**；主路径仍进程内 `_index` |
  | `config.cache_backend` 等 | [`src/config.py`](09%20生成答案评估，缓存策略与批量处理/src/config.py) | `memory` → 可扩 `sqlite`/`redis`；另有 `ttl_policy` 等键 | 键已预留，**默认未读** |
  | `link_signals_with_sources` | `answer_evaluator.py` | 幻觉软信号联合引用降权 | 占位透传 |
  | `extensions` 字段 | `PipelineWithEval` 结果 | 挂持久化元数据 / 附加分 | 预留 |

  > **注意**：`ModelAdapter` 解决的是「怎么统一调用生成」，`BaseCacheBackend` 解决的是「答案缓存以后怎么落盘」——**都不是**会话 `session_id` 历史库。11 会话持久化应自建 SessionStore 后端；可抄分层模式。详见 [`笔记/11笔记.md`](笔记/11笔记.md) Q5。
- **CLI**：
  ```powershell
  # 样本 offline（默认）
  python scripts/run_eval_cache_batch.py --mode offline
  # 全量 live（等价 notebook C5；耗时长）
  python scripts/run_eval_cache_batch.py --mode live --retrieval-mode full --check-only
  python scripts/run_eval_cache_batch.py --mode live --retrieval-mode full --max-workers 2
  # BM25 分片索引构建
  python scripts/build_bm25_full_index.py --shard-size 100000
  ```
- **后续开发注意**（[`schedule.md`](09%20生成答案评估，缓存策略与批量处理/schedule.md) 阶段 7）：
  - 样本 §4 指标**不能外推**全量质量；全量对照见报告 §6。
  - 生成缓存命中**不跳过检索**（`resolve_context_text` 先跑）；检索是 live 第二大瓶颈。
  - 大文件现位于 `Dataset/processed/`、`Dataset/bm25/` **不进 Git**；E: 作手动备份。
  - 跨阶段 `bootstrap`/`config`/`models` 同名冲突由 `full_eval.py` 处理。
- **详情**：[`schedule.md`](09%20生成答案评估，缓存策略与批量处理/schedule.md)；[`09笔记.md`](笔记/09笔记.md) Q5/Q6（耗时与分片 BM25）

### 跨阶段：样本库 → 全量生产（LangChain_RAG 前必读）

| 环节 | 开发默认 | 生产（阶段 7 已打通） |
|------|----------|----------------------|
| 向量检索 | `Dataset/chroma/chroma_db` / 1,267 | `Dataset/chroma/chroma_db_full` / 610 万 |
| BM25 语料 | `chunks_sample.jsonl` | `Dataset/processed/oa_comm_chunks.jsonl` |
| BM25 索引 | 现场 build | `Dataset/bm25/bm25_full/`（分片） |
| 检索 | `from_mode("sample")` | **`from_mode("full")`** |
| 生成评测 | 08 样本 `pipeline_eval.json` | live 全量 pipeline（可选 08 重跑快照） |
| 答案评估 | 09 offline 样本指标（§4） | **09 live full**（§6 / `--retrieval-mode full`） |
| **10 强约束** | 单元/陷阱用 fixture · mock 报告 | **默认 full 路径** + `adversarial_eval_report_full.json` |
| **11 HTTP API** | 进程默认 `sample` · mock 契约 | 显式 `MED_RAG_RETRIEVAL_MODE=full` + `run_full_api_smoke.py` |
| **12 ops API** | sample + documents_sample · C0–C4 | 阶段 5：`full` + documents_full + Ollama（`api-ops-full`） |

出处：[`06 schedule`](06%20检索系统开发第二部分/schedule.md)、[`09 schedule`](09%20生成答案评估，缓存策略与批量处理/schedule.md) 阶段 7、报告 §6、[`Dataset/README.md`](Dataset/README.md)、[`11 报告`](11%20服务化与接口开发第一部分/docs/服务化接口报告.md) §4。

### 10 强约束规则开发与幻觉抑制（✅ 已完成）

> **交付物速查**：代码 + notebook C0–C6 + mock 对抗报告 + 正式报告已齐。

| 项 | 路径 / 命令 |
|----|-------------|
| 计划 | [`schedule.md`](10%20强约束规则开发与幻觉抑制/schedule.md) 阶段 0–6 |
| Notebook | [`constraint-hallucination.ipynb`](10%20强约束规则开发与幻觉抑制/notebooks/constraint-hallucination.ipynb)（规则/mock）· [`constraint-mvp-observe.ipynb`](10%20强约束规则开发与幻觉抑制/notebooks/constraint-mvp-observe.ipynb)（真模型输出 MVP） |
| CLI mock | `python scripts/run_adversarial_eval.py --mock` |
| CLI live | `python scripts/run_adversarial_eval.py --mode live --retrieval-mode full --fixture-only` |
| 样例报告 | [`adversarial_eval_report_full.json`](10%20强约束规则开发与幻觉抑制/outputs/samples/adversarial_eval_report_full.json) |
| 正式报告 | [`docs/强约束与幻觉抑制报告.md`](10%20强约束规则开发与幻觉抑制/docs/强约束与幻觉抑制报告.md) |
| 笔记 | [`10笔记.md`](笔记/10笔记.md) |

- **mock 指标（2026-07-14 notebook / CLI）**：幻觉率 0.0 · 拒答命中 1.0 · 引用/格式/术语合规 1.0  
- **设计要点**：`append_to` · `assign_labels` · 格式别名 · `boundary_hit` 豁免 · journal/year `relaxed` · `max_retries=1`
- **依赖**：[`requirements.txt`](10%20强约束规则开发与幻觉抑制/requirements.txt)（复用环境；列 `pytest` / `httpx`）
- **主接口（供 11 挂载）**：`ConstrainedGenerationPipeline.from_mode("sample"|"full").run(query)` → `answer` / `sources` / `constraint_checks` / `retry_count` / `repaired`

### 11 服务化与接口开发第一部分（✅ 已完成 · 2026-07-25）

> **交付物速查**：FastAPI API 后端（非产品前端）+ notebook C0–C4.5 + full 抽检图文 + 正式报告（含前端接入契约）已齐。

| 项 | 路径 / 命令 |
|----|-------------|
| 计划 | [`schedule.md`](11%20服务化与接口开发第一部分/schedule.md) 阶段 0–5（含 4.5 全量抽检） |
| 启动 API | `cd "11 服务化与接口开发第一部分"` → `python scripts/run_api.py` → [`/docs`](http://127.0.0.1:8000/docs) · `/health` · `/ready` |
| 主接口 | `POST /api/v1/qa` · `POST /api/v1/qa/stream`（`stream_mode=pseudo`）· `GET /api/v1/sessions/{id}` |
| Notebook | [`api-smoke.ipynb`](11%20服务化与接口开发第一部分/notebooks/api-smoke.ipynb)（C0–C4.5） |
| 全量抽检 | `python scripts/run_full_api_smoke.py` → [`outputs/reports/`](11%20服务化与接口开发第一部分/outputs/reports/) |
| 正式报告 | [`docs/服务化接口报告.md`](11%20服务化与接口开发第一部分/docs/服务化接口报告.md)（§3 API 契约 · §4 full live） |
| 笔记 | [`11笔记.md`](笔记/11笔记.md)（Q4 伪/真流式 · Q6 任务书对照 · Q7 为何 `/` 空白） |
| Dataset | 只读 [`Dataset/`](Dataset/README.md)；模式见 `MED_RAG_RETRIEVAL_MODE` |

- **验证**：pytest **41 passed**；full live sync ≈ **180 s** · citation/format ok · HTTP 热身探针 200/`code=0`
- **⚠️ 边界**：无产品 Web UI、无鉴权、无会话持久化 DB、非 Ollama 真 token 流；浏览器打开 `/` 得 JSON 属预期
- **依赖**：[`requirements.txt`](11%20服务化与接口开发第一部分/requirements.txt)（`fastapi` · `uvicorn[standard]`）
- **后续注意**：前端按报告 §3 接线；CORS/鉴权待补；真流式需动 08 + 理顺 10 重试（见笔记 Q4）

### 12 服务化与接口开发第二部分（✅ 0–6 完成 · 2026-07-29）

> **交付物速查**：会话/统计/文档 API + 部署文档 + Postman + smoke C0–C4 + **全量仿真 F1+** + **正式报告** 已齐。

| 项 | 路径 / 命令 |
|----|-------------|
| 计划 | [`schedule.md`](12%20服务化与接口开发第二部分/schedule.md) 阶段 0–6 ✅ |
| 启动 API | `cd "12 服务化与接口开发第二部分"` → `copy .env.example .env` → `python scripts/run_api.py --no-reload` → [`/docs`](http://127.0.0.1:8000/docs) |
| 主接口 | `POST/GET/DELETE /api/v1/sessions` · `GET /api/v1/stats/{qa,index,health}` · `GET /api/v1/documents` · `GET /api/v1/documents/{pmcid}` ·（经 bridge）`POST /api/v1/qa` |
| Notebook | [`api-ops-smoke.ipynb`](12%20服务化与接口开发第二部分/notebooks/api-ops-smoke.ipynb)（C0–C4）· [`api-ops-full.ipynb`](12%20服务化与接口开发第二部分/notebooks/api-ops-full.ipynb)（F0+F1） |
| 全量仿真 CLI | `conda run -n med-rag-verify python scripts/run_full_ops_smoke.py`（先 `--check-only`） |
| 全量报告 | [`outputs/reports/full_ops_smoke.json`](12%20服务化与接口开发第二部分/outputs/reports/) · `full_ops_smoke_*.png` |
| stats 样例 | [`outputs/samples/`](12%20服务化与接口开发第二部分/outputs/samples/) |
| 正式报告 | [`docs/服务化接口第二部分报告.md`](12%20服务化与接口开发第二部分/docs/服务化接口第二部分报告.md) |
| Postman | [`postman/MedRAG_API.postman_collection.json`](12%20服务化与接口开发第二部分/postman/MedRAG_API.postman_collection.json) |
| 部署说明 | [`docs/部署与API调用说明.md`](12%20服务化与接口开发第二部分/docs/部署与API调用说明.md) §9 full |
| 文档索引 | [`Dataset/documents/`](Dataset/documents/README.md)（sample ✅ 1000 · full ✅ **4,557,627**） |
| 测试 | `pytest`（12 目录）**18 passed**（sample）；全量以 CLI/notebook 验收 |
| 笔记 | [`12笔记.md`](笔记/12笔记.md) |

- **错误码要点**：会话缺失 **3002**；文档缺失 **3001**；路由未命中 **1001**；`POST /qa` 无效 session **自动新建**
- **⚠️ 边界**：Windows 中文路径下 live `/qa` 走主线程 RagService（对齐 11）；无鉴权 / 无产品前端；Dataset sqlite **不进 Git**
- **依赖**：[`requirements.txt`](12%20服务化与接口开发第二部分/requirements.txt)（相对 11 新增 **`python-dotenv`**）
- **后续**：产品打包交付见 [`Med-RAG/`](Med-RAG/) · 计划 [`final-schedule`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/final-schedule.md)

### 打包 · Med-RAG（✅ Demo 已落地 · 2026-08）

> **交付物速查**：自包含 FastAPI + React 双栏聊天 + 会话落盘 + sample 上传 ingest + 四份 docs + zip 脚本已齐。

| 项 | 路径 / 命令 |
|----|-------------|
| 计划 | [`final-schedule.md`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/final-schedule.md)（P0–P4 ✅） |
| 包入口 | [`Med-RAG/README.md`](Med-RAG/README.md) |
| 启动 API | `cd Med-RAG` → `copy .env.example .env` → `python backend/scripts/run_api.py --no-reload` → `/docs` |
| 启动 UI | `cd Med-RAG/frontend` → `npm install` → `npm run dev` → `http://127.0.0.1:5173` |
| 主接口 | `/api/v1/qa` · `/sessions` · `/stats/*` · `/documents` · 上传 ingest · 站内 `/docs/{slug}` |
| 文档 | [`部署`](Med-RAG/docs/%E9%83%A8%E7%BD%B2%E6%96%87%E6%A1%A3.md) · [`代码说明`](Med-RAG/docs/%E4%BB%A3%E7%A0%81%E8%AF%B4%E6%98%8E%E6%96%87%E6%A1%A3.md) · [`数据导入`](Med-RAG/docs/%E6%95%B0%E6%8D%AE%E5%AD%98%E5%82%A8%E4%B8%8E%E5%AF%BC%E5%85%A5%E5%8F%82%E8%80%83.md) · [`流程图`](Med-RAG/docs/%E6%B5%81%E7%A8%8B%E5%9B%BE.md) |
| 数据 | `Med-RAG/data/`（大文件 gitignore）；迁入说明见数据导入文档；共享盘 [Drive](https://drive.google.com/drive/folders/1uK-2nbpOAWH61pWWrArpR8fdUzUihZ7H?usp=sharing) |
| 依赖 | [`Med-RAG/requirements.txt`](Med-RAG/requirements.txt) + Node（frontend） |

- **⚠️ 边界**：一期上传**只写 sample**；full 为预建资产只读问答；无 Docker（二期可选）；运行时不依赖 `../11` 等兄弟目录
- **后续**：Compose / 真流式 / 鉴权等见 [`（未来优化）`](%EF%BC%88%E6%9C%AA%E6%9D%A5%E4%BC%98%E5%8C%96%EF%BC%89%E6%89%93%E5%8C%85%E5%90%8E%E6%95%B0%E6%8D%AE%E6%9B%B4%E6%96%B0/) 与 final-schedule 二期项

---

## 笔记目录

`笔记/` 下为**个人学习 Q&A**，记录概念与踩坑，**不属于正式交付物**。

| 文件 | 内容 |
|------|------|
| `01笔记.ipynb` | 量化机制、Ollama 存储原理 |
| `01笔记附chroma.ipynb` | Chroma 工作机制 |
| `02笔记.ipynb` | 数据质量问题诊断与修复 |
| `03笔记.md` | 第三阶段任务理解 Q&A |
| `04笔记.md` | 嵌入模型、维数、token、ChromaDB、BGE 查询指令 Q&A |
| `05笔记·.md` | 05 阶段共识、filter 决策、双库 smoke、notebook 实测 Q&A |
| `06笔记.md` | 06 阶段 RAG 位置、多路检索/融合/rerank 概念 Q&A |
| `07 笔记.md` | 07 阶段 RAG 位置、输入契约、冒烟测试 Q&A |
| `08笔记.md` | 08 阶段 RAG 位置、schedule 审阅、与 07 衔接 Q&A |
| `09笔记.md` | 09 阶段任务定位、评估/缓存/批量设计、全量耗时与分片 BM25（Q5/Q6） |
| `10笔记.md` | 10 阶段定位（08/09/10 对照）、schedule 审阅、全量优先、`max_retries`、临时编号回查（Q4） |
| `11笔记.md` | 11 定位、全量 Dataset（Q3）、伪/真流式（Q4）、会话持久化（Q5）、任务书对照（Q6）、API 非前端（Q7） |
| `12笔记.md` | 12 定位、计划审阅、全库文档索引与打包规划（Q5–Q11） |


---

## 更新记录

| 日期 | 说明 |
|------|------|
| 2026-05-11 ~ 13 | 01 阶段完成：本地 LLM + PMC 数据源验证 |
| 2026-05-15 ~ 27 | 02 阶段完成：全量 slim 4,557,627 篇，分割策略验证通过 |
| 2026-05-27 | 03 阶段完成：6,107,296 chunks |
| 2026-06-01 ~ 03 | 04 阶段完成：全量 Chroma 建库 + GPU 环境 |
| 2026-06-08 ~ 10 | 05 阶段完成：查询理解与增强 |
| 2026-06-15 ~ 18 | 06 阶段完成：检索流水线 + 样本/全量联调 |
| 2026-06-22 ~ 24 | 07 阶段完成：上下文组装 + Prompt 模板 |
| 2026-06-29 ~ 07-02 | 08 阶段完成：Ollama 生成流水线 + `generation_eval.json` |
| 2026-07-07 ~ 08 | 09 阶段完成（0–7）：评估/缓存/批量；分片 BM25；全量 live；06 联动 |
| 2026-07-08 | README 结构重组与阶段 7 交付物速查对齐 |
| 2026-07-13 | 10 阶段启动（计划）：任务书 + `schedule.md` |
| 2026-07-14 ~ 15 | 10 阶段 0–6：约束层 + 对抗评测 + 正式报告；pytest 43 |
| 2026-07-16 | Dataset 统一迁入；见 [`Dataset/README.md`](Dataset/README.md) |
| 2026-07-23 | 11 启动规划：任务书 + `schedule.md` + [`11笔记.md`](笔记/11笔记.md) |
| 2026-07-24 | 11 阶段 0–3：骨架 · 契约 · RagService/会话 · 同步 `/qa`；pytest 递增至 35 |
| 2026-07-25 | 11 阶段 4–5 完成：伪 SSE · full live 抽检 · [`服务化接口报告.md`](11%20服务化与接口开发第一部分/docs/服务化接口报告.md)；pytest **41**；Dataset README / 根 README 对齐结案 |
| 2026-07-27 | 12 规划定稿：全库文档索引（`Dataset/documents`）；`chunks_sample` 复制进 Dataset；[`打包资产清单`](Dataset/打包资产清单.md)；[`（打包）02schedule`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/02schedule.md)；[`（未来优化）数据更新`](%EF%BC%88%E6%9C%AA%E6%9D%A5%E4%BC%98%E5%8C%96%EF%BC%89%E6%89%93%E5%8C%85%E5%90%8E%E6%95%B0%E6%8D%AE%E6%9B%B4%E6%96%B0/schedule.md)；[`12笔记`](笔记/12笔记.md) Q8 |
| 2026-07-27 | 文档索引构建改为逻辑分片（批 upsert + `progress.json` 断点）；更新 documents README、12 / 未来优化 schedule、[`12笔记`](笔记/12笔记.md) Q9 |
| 2026-07-27 | 阶段 12·0 完成：骨架 + `bridge11`；`documents/sample`（1000）；smoke/full notebook |
| 2026-07-27 | 阶段 12 requirements 对齐；`install_all_requirements.ps1` 含 12；documents/full 建成（4,557,627 · ~11.5 GB） |
| 2026-07-28 | 阶段 12·1–4 完成：sessions / stats / documents API；Postman + 部署说明；smoke C0–C4；pytest 18 |
| 2026-07-28 | 根 README 对齐 12·0–4；`.gitignore` 忽略运行日志与 notebook fixture |
| 2026-07-29 | 阶段 12·5–6 完成：full ops smoke + [`服务化接口第二部分报告`](12%20服务化与接口开发第二部分/docs/服务化接口第二部分报告.md)；`stage=12-6` |
| **2026-08-06** | **Med-RAG 产品打包落地**：[`Med-RAG/`](Med-RAG/)（FastAPI + React Demo）；[`final-schedule`](%EF%BC%88%E6%89%93%E5%8C%85%EF%BC%89LangChain_RAG/final-schedule.md) P0–P4；sample/full 角色与上传写 sample；[Drive Dataset](https://drive.google.com/drive/folders/1uK-2nbpOAWH61pWWrArpR8fdUzUihZ7H?usp=sharing)；根 README / Dataset 清单对齐 GitHub 提交准备 |

*阶段进度细节以各目录 `schedule.md` / `Med-RAG` docs「进度记录」为准。*
