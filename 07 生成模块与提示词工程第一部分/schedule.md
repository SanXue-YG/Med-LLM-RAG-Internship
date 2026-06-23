# 07 生成模块与提示词工程第一部分 — 执行计划

> **状态：🔄 待启动**
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

### 阶段 1：数据结构定义（DocumentChunk / 汇总 metadata） ☐

- [ ] `@dataclass DocumentChunk`（按任务书字段）
  - [ ] `text: str`
  - [ ] `metadata: Dict[str, Any]`
  - [ ] `relevance_score: float`
  - [ ] `source: str`
  - [ ] `chunk_id: str`
- [ ] 定义组装结果结构（建议）
  - [ ] `context_text: str`
  - [ ] `metadata: dict`
  - [ ] `selected_chunks: list[DocumentChunk]`

### 阶段 2：上下文组装器（ContextAssembler） ☐

- [ ] tokenizer 加载（可配置 `tokenizer_name`；默认与现有环境兼容）
- [ ] `estimate_tokens(text)`：估算 token 数
- [ ] 输入转换：将 06 候选 dict 转为 `DocumentChunk`
- [ ] 去重：Jaccard 相似度
  - [ ] 可配置：`dedup_threshold`（如 0.85）
  - [ ] 输出：`unique_chunks_after_dedup`
- [ ] 排序：按 `relevance_score`（或多字段）
- [ ] 多样化：同一来源（如 `doc_id` / `source_title`）超过阈值时降优先级
- [ ] 截断：不超过 `max_context_tokens`
  - [ ] “末 10% 句号截断”策略落地
- [ ] 产出 metadata：
  - [ ] `total_chunks_retrieved`
  - [ ] `unique_chunks_after_dedup`
  - [ ] `chunks_selected`
  - [ ] `estimated_tokens`
  - [ ] `chunk_sources`（来源分布统计）

### 阶段 3：医学提示工程模板（PromptStage） ☐

- [ ] `@dataclass PromptStage`
  - [ ] `name: str`
  - [ ] `system_prompt: str`
  - [ ] `user_prompt_template: str`
  - [ ] `temperature: float`
  - [ ] `max_tokens: int`
- [ ] `PROMPT_STAGES` 四阶段模板（任务书建议结构）
  - [ ] `evidence_evaluator`：证据质量/一致性检查
  - [ ] `answer_generator`：基于上下文回答（引用证据点）
  - [ ] `critical_reviewer`：挑错与风险声明（医学安全）
  - [ ] `final_assembler`：合并为最终输出格式
- [ ] 模板占位符统一（建议）：`{question}`、`{context}`、`{constraints}`、`{output_format}`

### 阶段 4：Notebook 演示与样例导出 ☐

- [ ] `notebooks/generation-prompting.ipynb`
  - [ ] C0：从 06 pipeline 取候选（样本模式即可）
  - [ ] C1：ContextAssembler 组装 + metadata 展示
  - [ ] C2：去重/多样化前后对比
  - [ ] C3：截断策略演示（token 限制 + 句号截断）
  - [ ] C4：四阶段 prompt 渲染示例（不一定真实调用 LLM）
  - [ ] C5：导出样例 JSON
- [ ] 输出：
  - [ ] `outputs/samples/assembled_context_examples.json`
  - [ ] `outputs/samples/prompt_examples.json`

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

