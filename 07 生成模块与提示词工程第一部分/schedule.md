# 07 生成模块与提示词工程第一部分 — 执行计划

> **状态：🔄 进行中（阶段 0–2 ✅；阶段 3–5 待做）**
>
> **本阶段范围（任务书）**：完成「上下文组装器（Context Assembler）」与「医学提示工程模板（Prompt Stages）」两部分代码，为后续 RAG 答案生成链路做准备。
>
> **上游依赖**：
> - 06：检索流水线输出候选文档块（向量 + BM25 + 融合 + 重排）
> - 05：`EnhancedQuery`（query 清洗/扩展/filters）
> - 04：向量库与 `ChromaIndexBuilder.query()`（用于端到端 smoke）

---

## 任务书目标对照

| 任务书要求 | 本阶段交付 |
|------------|------------|
| 定义文档块数据类 `DocumentChunk` | `src/models.py`：`@dataclass DocumentChunk` |
| 完成上下文组装器 `ContextAssembler` | `src/context_assembler.py`：去重、排序、多样化、截断、metadata 汇总 |
| tokenizer 加载与 token 估算 | `ContextAssembler.estimate_tokens()`（与现有环境兼容） |
| 文档相似性去重（Jaccard） | `ContextAssembler.dedup_by_jaccard()` |
| 医学提示工程模板（PromptStage） | `src/prompts.py`：`PromptStage` + 四阶段模板 |
| 参考结构：evidence_evaluator/answer_generator/critical_reviewer/final_assembler | `PROMPT_STAGES` 字典 + 可配置温度/长度 |

---

## 关键约束与设计决策（启动前）

| 项 | 决策 | 说明 |
|----|------|------|
| 端到端范围 | 本周只做 **上下文组装 + prompt 模板** | 不强依赖具体 LLM 接口（Ollama/LangChain 后续） |
| 输入数据格式 | 兼容 06 的候选列表（含 `text/metadata/score/source/chunk_id`） | 07 做一层转换为 `DocumentChunk` |
| token 估算 | **可运行优先**：先用轻量估算，再可选接入 tokenizer 精估 | 任务书要求“加载 tokenizer”；但不同模型 tokenizer 不统一 |
| 去重策略 | Jaccard（token 集合）为主，阈值可配 | 任务书建议；避免重复 chunk 影响上下文 |
| 多样化策略 | 同一 `doc_id/source_title` 过多时降权 | 避免上下文全来自同一篇/同一来源 |
| 截断策略 | 保证在段落/句号处截断（末 10% 搜索句号） | 任务书明确要求 |

---

## 模块设计

### 目录结构（规划）

```text
07 生成模块与提示词工程第一部分/
├── 任务.txt
├── schedule.md                      # 本文件
├── 输入候选格式约定.md              # 上游 06 → 07 输入契约（阶段 0 产出）
├── requirements.txt                 # tokenizer / 文本相似度依赖（尽量少）
├── src/
│   ├── __init__.py
│   ├── models.py                    # DocumentChunk / AssembledContext
│   ├── context_assembler.py         # ContextAssembler
│   ├── prompts.py                   # PromptStage + 模板集合
│   └── pipeline.py                  # （可选）retrieve→assemble→prompt 的轻量粘合层
├── notebooks/
│   └── generation-prompting.ipynb   # C0–C6：组装与 prompt 演示
├── tests/
│   ├── test_dedup.py
│   ├── test_truncate.py
│   └── test_prompts.py
└── outputs/
    └── samples/
        ├── assembled_context_examples.json
        └── prompt_examples.json
```

---

## 分阶段执行

### 阶段 0：环境与骨架 ✅

- [x] 创建 `src/`、`notebooks/`、`tests/`、`outputs/samples/`（含 `__init__.py` / `.gitkeep` 占位）
- [x] `requirements.txt`：复用 `med-rag-verify`（02/04/05/06 同环境）；本阶段**无强制新增依赖**（组装/模板为纯 Python，token 估算复用已装 `transformers` tokenizer）
- [x] 约定输入候选格式：见 [`输入候选格式约定.md`](输入候选格式约定.md)（06 `result["reranked"]` / 退化 `["retrieval"]["fused"]` 的候选 dict → `DocumentChunk` 映射）

### 阶段 1：数据结构定义（DocumentChunk / 汇总 metadata） ✅

- [x] `@dataclass DocumentChunk`（按任务书字段）
  - [x] `text: str`
  - [x] `metadata: Dict[str, Any]`
  - [x] `relevance_score: float`
  - [x] `source: str`
  - [x] `chunk_id: str`
- [x] 定义组装结果结构（`AssembledContext` + `ContextMetadata`）
  - [x] `context_text: str`
  - [x] `metadata: dict`（`ContextMetadata.to_dict()`）
  - [x] `selected_chunks: list[DocumentChunk]`
- [x] 06 候选转换：`document_chunk_from_candidate()` / `coerce_to_document_chunks()`（见 `src/models.py`，映射规则同 `输入候选格式约定.md` §3）

#### 阶段 1 交付回顾（2026-06-23）

| 产物 | 路径 | 说明 |
|------|------|------|
| 文档块数据类 | `src/models.py` → `DocumentChunk` | 任务书 5 字段：`text` / `metadata` / `relevance_score` / `source` / `chunk_id`；含 `to_dict()` |
| 组装统计结构 | `src/models.py` → `ContextMetadata` | 对应任务书 `context_metadata`；额外 `skipped_invalid` 记录转换跳过数 |
| 组装结果结构 | `src/models.py` → `AssembledContext` | `context_text` + `metadata` + `selected_chunks`；供阶段 2 `assemble()` 返回；含 `to_dict()` |
| 单条转换 | `document_chunk_from_candidate(dict)` | 06 候选 dict → `DocumentChunk`；`text` 无效返回 `None` |
| 批量转换 | `coerce_to_document_chunks(list)` | 兼容 `dict` / `DocumentChunk` 混合输入；返回 `(chunks, skipped_count)` |
| 包导出 | `src/__init__.py` | 上述符号均已 `__all__` 导出 |

**映射规则摘要**（详见 [`输入候选格式约定.md`](输入候选格式约定.md) §3）：

| `DocumentChunk` 字段 | 取值 |
|---------------------|------|
| `chunk_id` | `chunk_id` → `doc_id` → `unknown_{index}` |
| `relevance_score` | `final_score` → `fusion_score` → `relevance_score` → `score` → `0.0` |
| `source` | `source_title` → `doc_id` → `source`（召回通道名） |
| `metadata` | 候选 dict 中除 `text` 外全部字段原样收纳 |

**阶段 1 冒烟测试**（开发期快速验证，非正式 `tests/`）：用 06 离线样例 `outputs/samples/pipeline_eval.json` 中 `metformin cardiovascular effects` 的 `reranked`（5 条）与 `fused`（前 3 条）验证转换与回退规则；详见 [`笔记/07 笔记.md`](../笔记/07%20笔记.md) Q8。

### 阶段 2：上下文组装器（ContextAssembler） ✅

- [x] tokenizer 加载（可配置 `tokenizer_name`；默认 `gpt2`；`None` 时退化为字符启发式 `len//4`）
- [x] `estimate_tokens(text)`：估算 token 数
- [x] 输入转换：将 06 候选 dict 转为 `DocumentChunk`（复用 `coerce_to_document_chunks`）
- [x] 去重：Jaccard 相似度
  - [x] 可配置：`dedup_threshold`（默认 `0.85`）
  - [x] 输出：`unique_chunks_after_dedup`
- [x] 排序：按 `relevance_score` 降序
- [x] 多样化：同一 `doc_id` / `source_title` 超过 `max_per_source`（默认 2）时按 `source_penalty` 降权
- [x] 截断：不超过 `max_context_tokens`
  - [x] “末 10% 句号截断”策略落地（该区间无句号则硬截断）
- [x] 产出 metadata：
  - [x] `total_chunks_retrieved`
  - [x] `unique_chunks_after_dedup`
  - [x] `chunks_selected`
  - [x] `estimated_tokens`
  - [x] `chunk_sources`（来源分布统计）

#### 阶段 2 交付回顾（2026-06-23）

| 产物 | 路径 | 说明 |
|------|------|------|
| 上下文组装器 | `src/context_assembler.py` → `ContextAssembler` | `assemble()` → `AssembledContext`；`assemble_dict()` 对齐任务书 dict 返回 |
| 去重 | `dedup_by_jaccard()` | 英文轻量分词 + Jaccard；保留 `relevance_score` 更高者 |
| 多样化 | `_order_with_diversity()` | 同源超过 `max_per_source` 条时递减有效分 |
| 控长拼接 | `_build_context()` + `_truncate_to_tokens()` | 按块拼接 `chunk_separator`（默认 `\n\n`）；末块可部分截断 |
| 句号边界 | `_truncate_at_sentence_boundary()` | 在截断后文本**末 10%** 内找 `.` `!` `?` |
| 默认参数 | 模块常量 | `DEFAULT_TOKENIZER_NAME=gpt2`，`dedup_threshold=0.85`，`max_per_source=2`，`source_penalty=0.15` |

**阶段 2 冒烟测试**（`tokenizer_name=None` 启发式 token）：`pipeline_eval.json` → `metformin cardiovascular effects` 的 5 条 `reranked`，`max_context_tokens=800` → 入选 2 块、约 796 tokens、2 个不同 `doc_id`；另验证 Jaccard 去重与句号截断。

### 阶段 3：医学提示工程模板（PromptStage） ✅

- [x] `@dataclass PromptStage`
  - [x] `name: str`
  - [x] `system_prompt: str`
  - [x] `user_prompt_template: str`
  - [x] `temperature: float`
  - [x] `max_tokens: int`
- [x] `PROMPT_STAGES` 四阶段模板（任务书建议结构）
  - [x] `evidence_evaluator`：证据质量/一致性检查
  - [x] `answer_generator`：基于上下文回答（引用证据点）
  - [x] `critical_reviewer`：挑错与风险声明（医学安全）
  - [x] `final_assembler`：合并为最终输出格式
- [x] 模板占位符统一：`{question}`、`{context}`、`{constraints}`、`{output_format}`

#### 阶段 3 交付回顾（2026-06-23）

| 产物 | 路径 | 说明 |
|------|------|------|
| 提示阶段数据类 | `src/prompts.py` → `PromptStage` | 定义 `name/system_prompt/user_prompt_template/temperature/max_tokens` |
| 四阶段模板 | `src/prompts.py` → `PROMPT_STAGES` | `evidence_evaluator`、`answer_generator`、`critical_reviewer`、`final_assembler` |
| 渲染接口 | `render_user_prompt()` / `to_payload()` / `render_prompt_stage()` | 统一填充占位符并输出可直接调用 LLM 的 payload |
| 占位符校验 | `validate_prompt_stage()` | 检查模板是否包含四个统一占位符 |
| 包导出 | `src/__init__.py` | 导出 `PromptStage`、`PROMPT_STAGES`、`PROMPT_PLACEHOLDERS` 等 |

**阶段 3 冒烟测试**：验证 4 个 stage key 完整、每个模板占位符齐全，并可用同一组 `{question, context, constraints, output_format}` 成功渲染。

### 阶段 4：Notebook 演示与样例导出 ✅

- [x] `notebooks/generation-prompting.ipynb`
  - [x] C0：从 06 pipeline 取候选（样本模式即可）
  - [x] C1：ContextAssembler 组装 + metadata 展示
  - [x] C2：去重/多样化前后对比
  - [x] C3：截断策略演示（token 限制 + 句号截断）
  - [x] C4：四阶段 prompt 渲染示例（不一定真实调用 LLM）
  - [x] C5：导出样例 JSON
- [x] 输出：
  - [x] `outputs/samples/assembled_context_examples.json`
  - [x] `outputs/samples/prompt_examples.json`

#### 阶段 4 交付回顾（2026-06-23）

| 产物 | 路径 | 说明 |
|------|------|------|
| 演示 notebook | `notebooks/generation-prompting.ipynb` | 按 C0–C5 组织，包含通俗说明与可执行代码 |
| C0 数据加载 | notebook C0 | 加载 06 离线样例 `pipeline_eval.json` 与 07 模块 |
| C1 组装演示 | notebook C1 | 展示 `ContextAssembler.assemble()` 输出与 metadata |
| C2 策略对比 | notebook C2 | 对比 raw / dedup / diversity 顺序变化 |
| C3 截断演示 | notebook C3 | 不同 `max_context_tokens` 下长度与尾部边界表现 |
| C4 Prompt 渲染 | notebook C4 | 四阶段模板校验与 payload 渲染（不调 LLM） |
| C5 样例导出 | notebook C5 | 导出组装样例与 prompt 样例 JSON |

**阶段 4 运行结果（本次已生成）**：

- `outputs/samples/assembled_context_examples.json`
- `outputs/samples/prompt_examples.json`

### 阶段 5：测试与交付 ☐

- [ ] `test_dedup.py`：Jaccard 去重正确性与边界
- [ ] `test_truncate.py`：截断不破坏段落；末 10% 句号策略生效
- [ ] `test_prompts.py`：四阶段模板字段齐全、占位符可渲染
- [ ] 更新根目录 `README.md`：阶段 07 条目（完成后）
- [ ] （可选）阶段报告（若老师需要 docs，参照 04/05 写法）

---

## 验证用例（首批）

| # | 输入问题（英文） | 关注点 |
|---|------------------|--------|
| 1 | `metformin cardiovascular effects` | 上下文是否覆盖多篇证据、去重是否有效 |
| 2 | `MI treatment guideline` | 缩写扩展后候选是否更相关；prompt 是否要求引用依据 |
| 3 | `papers on malaria after 2015` | recency 在 06 若已体现，07 是否保留元数据以便表述 |
| 4 | `warfarin atrial fibrillation elderly` | 长尾关键词召回 + 上下文多样化 |

---

## 交付产物清单（预填）

| 产物 | 格式 | 路径 | Git |
|------|------|------|-----|
| 文档块数据类 | Python | `src/models.py` | ✅ |
| 上下文组装器 | Python | `src/context_assembler.py` | ✅ |
| 提示工程模板 | Python | `src/prompts.py` | ✅ |
| 演示 notebook | `.ipynb` | `notebooks/generation-prompting.ipynb` | ✅ |
| 组装样例输出 | JSON | `outputs/samples/assembled_context_examples.json` | ✅ |
| prompt 渲染样例 | JSON | `outputs/samples/prompt_examples.json` | ✅ |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| tokenizer 与实际 LLM 不一致 | token 估算偏差 | 先用估算保证可运行；后续按目标 LLM 统一 tokenizer |
| 去重过强导致召回下降 | 上下文信息不足 | 去重阈值可调；保留“同 doc_id 多块”最低配额 |
| 多样化过强导致相关性下降 | 证据变散 | 先 relevance 排序，再轻量惩罚同源 |
| 截断破坏语义 | prompt 难用 | 强制在句号/段落边界截断 |

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-06-22 | 创建阶段 07 `schedule.md`（对齐任务书要求，待启动实施） |
| 2026-06-22 | **阶段 0 完成**：搭建 `src/`/`notebooks/`/`tests/`/`outputs/samples/` 骨架；`requirements.txt` 复用 `med-rag-verify` 无强制新增；新增 `输入候选格式约定.md`（06 reranked/fused → `DocumentChunk` 映射） |
| 2026-06-23 | **阶段 1 完成**：`src/models.py` — `DocumentChunk`、`ContextMetadata`、`AssembledContext`；`document_chunk_from_candidate` / `coerce_to_document_chunks` 对接 06 候选 |
| 2026-06-23 | **阶段 2 完成**：`src/context_assembler.py` — `ContextAssembler`（Jaccard 去重、多样化、token 控长、句号截断）；样本 query 冒烟通过 |
| 2026-06-23 | **阶段 3 完成**：`src/prompts.py` — `PromptStage` + 四阶段 `PROMPT_STAGES` + 统一占位符渲染与校验；模板冒烟通过 |
| 2026-06-23 | **阶段 4 完成**：`generation-prompting.ipynb`（C0–C5 详解）+ 导出 `assembled_context_examples.json`、`prompt_examples.json` |

