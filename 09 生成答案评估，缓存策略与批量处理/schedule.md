# 09 生成答案评估，缓存策略与批量处理 — 执行计划

> **状态：🔄 待启动**
>
> **本阶段范围（任务书）**：实现 **多维度答案评估器**、**生成结果缓存**、**批量并行处理（optional）**；并用 08 阶段固定测试 query 复跑，验证评估 / 缓存 / 批量功能。
>
> **上游依赖**：
> - 08：`MedicalGenerationPipeline`、`LLMGenerator`、`generation_eval.json`（4 条基准 query 与答案快照）
> - 07：`ContextAssembler`（缓存键需含组装后 `context_text`）
> - 06：`RetrievalPipeline`（批量生成时的检索输入）

---

## 任务书目标对照

| 任务书要求 | 本阶段交付 |
|------------|------------|
| 多维度评估指标 | `src/answer_evaluator.py` → `AnswerEvaluator.evaluate()` |
| a) 文本相似性（ROUGE） | `rouge` 库；对比生成答案 vs 参考答案 |
| b) 关键信息提取评估 | 正则提取医学字段；`recall = overlap / gt_matches` |
| c) 幻觉检测 | 绝对化/无引用表述信号；风险分数 |
| 可读性评估 | 平均句长、句子数等 |
| 缓存键（query + context 哈希） | `src/generation_cache.py` |
| 缓存大小限制 / TTL / 低温才缓存 | `LRUCache` + `max_entries` + `ttl_seconds` + `max_temperature` |
| 批量处理（optional） | `src/batch_runner.py`：`ThreadPoolExecutor` |
| 复跑上周测试 query | notebook + CLI；对比缓存命中与评估指标 |

---

## 关键约束与设计决策（启动前）

| 项 | 决策 | 说明 |
|----|------|------|
| 参考答案（ground truth） | `data/ground_truth.json`（4 条，与 08 `DEFAULT_QUERIES` 对齐） | ROUGE 与关键信息 recall 需参考答案；可基于 08 快照人工整理要点 |
| 评估语言 | **英文**（与语料 / 生成答案一致） | 正则与 ROUGE 均按英文设计 |
| 缓存存储 | **进程内 LRU**（首版）；可选落盘 JSON | 任务书强调防 OOM；首版不强制 Redis |
| 缓存键材料 | `hash(query + context_text + model_name + temperature)` | 相同输入相同输出；温度变化不命中 |
| 可缓存条件 | `temperature <= 0.3`（可配）且生成成功 | 任务书：只缓存低温度确定性结果 |
| TTL | 默认 **24h～7d**（可配） | 医学知识有时效性，不永久缓存 |
| 批量并行 | `ThreadPoolExecutor`，`max_workers = min(4, cpu_count)` | 任务书 optional；Ollama 单模型注意并发不宜过高 |
| 单任务失败 | 捕获异常，返回 `error` 字段，不中断整批 | 任务书明确要求 |
| 顺序一致 | `executor.map` 或带 index 的 `as_completed` 重排 | 输入输出顺序对齐 |
| 本阶段边界 | **不实现** 人工标注平台、在线 A/B、分布式缓存 | 属产品化 / 运维范畴 |

---

## 端到端数据流

```
query (+ 可选 force_refresh)
    ↓ cache lookup(key = hash(query, context, model, temp))
    ├─ HIT  → 直接返回缓存 result + cache_metadata
    └─ MISS → 08 MedicalGenerationPipeline.run()
              ↓ 若 temperature 够低 → cache.set(...)
    ↓ 09 AnswerEvaluator.evaluate(generated_answer, ground_truth, context?)
              ↓ metrics: rouge / key_info_recall / hallucination_risk / readability
汇总 result + evaluation + cache_stats
```

**批量路径**：

```
list[query] → BatchRunner.run_batch()
    → ThreadPoolExecutor（每任务：cache + pipeline + evaluate）
    → list[result]（顺序与输入一致）
```

---

## 模块设计

### 目录结构（规划）

```text
09 生成答案评估，缓存策略与批量处理/
├── 任务.txt
├── schedule.md                      # 本文件
├── requirements.txt                 # rouge-score 等
├── data/
│   └── ground_truth.json            # 4 条 query 的参考答案要点（可 git）
├── src/
│   ├── __init__.py
│   ├── bootstrap.py                 # sys.path 引用 05–08
│   ├── patterns.py                  # 关键信息 / 幻觉信号正则
│   ├── answer_evaluator.py          # AnswerEvaluator
│   ├── generation_cache.py          # GenerationCache
│   ├── batch_runner.py              # BatchRunner（optional）
│   └── pipeline_with_eval.py        # 粘合：cache + 08 pipeline + evaluate
├── notebooks/
│   └── answer-eval-cache-batch.ipynb  # C0–C8
├── scripts/
│   └── run_eval_cache_batch.py      # CLI：复跑 08 四条 + 导出报告
├── tests/
│   ├── test_answer_evaluator.py
│   ├── test_generation_cache.py
│   └── test_batch_runner.py
└── outputs/
    ├── samples/
    │   └── eval_cache_batch_report.json
    └── logs/
        └── eval_cache_batch_*.json
```

### 核心 API（草案）

```python
@dataclass
class EvaluationResult:
    rouge: dict[str, float]          # rouge-1/2/L F1
    key_info_recall: float
    key_info_matched: list[str]
    key_info_missing: list[str]
    hallucination_risk: float        # 0~1，信号越多越高
    hallucination_signals: list[str]
    readability: dict[str, float]   # avg_sentence_len, num_sentences, ...


class AnswerEvaluator:
    def evaluate(
        self,
        generated: str,
        ground_truth: str,
        *,
        context: str | None = None,
    ) -> EvaluationResult: ...


class GenerationCache:
    def make_key(
        self, query: str, context_text: str, model: str, temperature: float
    ) -> str: ...
    def get(self, key: str) -> dict | None: ...
    def set(self, key: str, value: dict, *, temperature: float) -> bool: ...
    # max_entries, ttl_seconds, max_temperature


class BatchRunner:
    def run_batch(
        self,
        queries: list[str],
        *,
        max_workers: int | None = None,
    ) -> list[dict]: ...
```

### 评估维度细则（对齐任务书）

#### a) ROUGE（文本相似性）

| 项 | 说明 |
|----|------|
| 库 | `rouge-score`（或 `rouge` 包，requirements 中固定版本） |
| 输入 | `generated_answer` vs `ground_truth["reference_answer"]` |
| 输出 | `rouge1` / `rouge2` / `rougeL` 的 F1（及可选 precision/recall） |

#### b) 关键信息提取

| 字段类型 | 正则/关键词示例 |
|----------|-----------------|
| 百分比 | `\d+(\.\d+)?%` |
| 剂量 | `\d+\s*(mg|g|ml|mcg|units?)` 等 |
| 时间范围 | `\d+\s*(days?|weeks?|months?|years?)` |
| 安全信息 | risk, side effect, adverse, contraindication |
| 治疗建议 | recommend, treatment, therapy, regimen |
| 作用机制 | mechanism, pathway, action, principle |

`recall = |matched_gt| / |gt_matches|`（gt 侧由 `ground_truth["key_phrases"]` 提供）

#### c) 幻觉检测（启发式）

| 信号 | 风险说明 |
|------|----------|
| `研究表明` / `studies show`（无 `[n]` 引用） | 缺具体引用 |
| `已被证明` / `has been proven` | 缺限定条件 |
| `100%` | 医学极少绝对百分比 |
| `完全(安全\|有效\|无害)` / `completely safe` | 过度绝对化 |

`hallucination_risk = min(1.0, signal_count * weight)`（权重可配）

#### d) 可读性

| 指标 | 计算 |
|------|------|
| `num_sentences` | 按 `.!?` 分句 |
| `avg_sentence_len` | 字符数 / 句数 |
| `avg_word_len` | 可选 |

---

## 分阶段执行

### Notebook 贯穿策略（新增）

- [ ] 采用**单一 notebook 贯穿式开发**：`notebooks/answer-eval-cache-batch.ipynb`
- [ ] 每完成一个阶段，立即补齐对应 C* 单元并保存输出，不等到最后统一补
- [ ] 阶段与单元映射：阶段 0→C0，阶段 1→C1，阶段 2→C2/C3，阶段 3→C4，阶段 4→C5，阶段 5→C6

### 固定实现路径（本周统一口径）

- [ ] 质量评估固定路径：`AnswerEvaluator.evaluate()` = `ROUGE + key_info_recall + hallucination_risk + readability`
- [ ] 缓存固定路径：`GenerationCache`（进程内 LRU + TTL + 低温门控）  
      `key = hash(query + context_text + model + temperature)`
- [ ] 批量固定路径：`BatchRunner.run_batch()`（多 query 并行；单 query 内部仍串行）
- [ ] 粘合固定路径：`pipeline_with_eval.run_with_cache_and_eval()` 统一输出  
      `{ generation, evaluation, cache }`
- [ ] 验证固定路径：以 08 `DEFAULT_QUERIES` 四条为最小验收集，notebook 与 CLI 双入口一致

### 暂不实施项（占位符与扩展抓手）

- [ ] 占位符：`persistent_cache_backend`（默认 `memory`；后续实际部署时可考虑`sqlite`/`redis`）
- [ ] 占位符：`evidence_linked_hallucination_scoring`（当前按预定规则划分风险；后续根据需要加“有引用降权（论文明确说明的内容降低风险评级）”）
- [ ] 占位符：`semantic_key_info_match`（当前短语/正则重叠；后续可考虑语义匹配）
- [ ] 占位符：`adaptive_ttl_policy`（当前固定时效 TTL；后续按 query 类型动态 TTL）
- [ ] 占位符：`auto_tune_max_workers`（当前静态并发；后续按失败率/延迟动态调整）

### 阶段 0：环境与骨架 ✅

- [x] 创建目录结构（`src/`、`data/`、`notebooks/`、`scripts/`、`tests/`、`outputs/`）
- [x] `requirements.txt`：`rouge-score`（+ 复用 08 `httpx` 等）
- [x] `src/bootstrap.py`：引用 05–08 模块路径
- [x] 准备 `data/ground_truth.json`（4 条，对齐 08 `DEFAULT_QUERIES`）
- [x] Notebook C0：环境初始化 + `ground_truth.json` 加载与字段校验
- [x] 固定口径写入配置：`src/config.py`（新增）统一存放 `ttl_seconds`、`max_entries`、`max_temperature`、`max_workers`
- [x] 预留扩展配置键：`cache_backend`、`ttl_policy`、`hallucination_weight_profile`（先不启用）

### 阶段 1：评估器（AnswerEvaluator） ✅

- [x] `patterns.py`：关键信息 + 幻觉信号正则（中英文关键词以英文为主）
- [x] `answer_evaluator.py`：
  - [x] `score_rouge(generated, reference)`
  - [x] `extract_key_info(text)` / `key_info_recall(generated, gt_phrases)`
  - [x] `detect_hallucination_signals(text)` → risk score
  - [x] `readability_metrics(text)`
  - [x] `evaluate()` 汇总为 `EvaluationResult`
- [x] 单元测试：固定字符串样例（含/不含剂量、100%、副作用词等）
- [x] Notebook C1：单条 `AnswerEvaluator` 演示（ROUGE + key recall + 幻觉 + 可读性）
- [x] 固定规则说明：将“幻觉分=风险信号，不是最终真伪裁定”写入模块 docstring 与 notebook 注释
- [x] 预留函数占位：`link_signals_with_sources()`（当前返回空/透传，后续联动引用降权）

**阶段 1 完成说明**

- 本阶段相当于先把“答案体检仪”做出来了：现在每条回答都能被自动打分，不再只靠肉眼判断好坏。
- 体检包含四个维度：和标准答案像不像（ROUGE）、关键医学点有没有漏（recall）、有没有绝对化风险表述（幻觉信号）、读起来是否顺畅（可读性）。
- 这一步的作用是给后续缓存和批量处理提供统一“质量刻度”，后面无论是单条还是批量跑，都能稳定产出可对比的评估结果。
- 当前幻觉分是“风险提醒”而不是“最终判错”，后续可再联动引用信息做降权修正。

**阶段 1 实现说明（代码路径 / 函数 / 方法）**

- `src/answer_evaluator.py`
  - `score_rouge(generated, reference)`：使用 `rouge_score.RougeScorer` 计算 `rouge1/rouge2/rougeL` 的 F1，衡量生成答案与标准答案的文本重叠度。
  - `key_info_recall(generated, gt_phrases)`：对 `ground_truth` 的关键词做规范化并在生成答案中匹配，计算 `recall = matched / total`，同时输出 `matched` 与 `missing` 列表。
  - `detect_hallucination_signals(text)`：按绝对化表述规则匹配信号并按权重累加风险分，得到 `hallucination_risk`（封顶 1.0）。
  - `readability_metrics(text)`：按句子和词统计可读性，输出句子数、词数、平均句长、平均词长。
  - `evaluate(...)`：统一汇总以上四类指标并返回 `EvaluationResult`，作为后续流水线标准输出。
  - `link_signals_with_sources(...)`：预留扩展点，当前透传；后续可做“有引用降权”。
- `src/patterns.py`
  - 集中维护评估规则：百分比/剂量/时间范围正则，安全/治疗/机制关键词，幻觉信号与权重配置。
- `tests/test_answer_evaluator.py`
  - 单测覆盖四个核心能力：ROUGE、key_info_recall、幻觉信号识别、`evaluate()` 汇总结果结构（当前 4 passed）。
- `notebooks/answer-eval-cache-batch.ipynb`
  - C1 单元串起“输入样例 -> `AnswerEvaluator.evaluate()` -> `result.to_dict()`”，用于直观看到四维指标输出。

### 阶段 2：缓存（GenerationCache） ✅

- [x] `make_key()`：`sha256(query + context_text + model + temperature_bucket)`
- [x] 进程内 LRU：`max_entries`（如 128）防 OOM
- [x] TTL：条目 `expires_at`；`get` 时过期删除
- [x] 温度门控：`temperature > max_temperature` 时不 `set`
- [x] 统计：`hits` / `misses` / `evictions` / `size`
- [x] 单元测试：同输入同键、TTL 过期、高温不缓存、LRU 淘汰
- [x] Notebook C2：缓存 miss → hit 对比（同 query 连跑两次）
- [x] Notebook C3：TTL 过期与高温不缓存演示
- [x] 明确首版缓存边界：进程退出即失效（写入 README/注释）
- [x] 预留后端接口：`BaseCacheBackend`（memory 已实现；sqlite/redis 仅接口占位）

**阶段 2 完成说明**

- 本阶段把“少重复写”落地了：同样的 query+context 组合，第一次计算后会进入缓存，第二次可直接命中返回。
- 缓存具备三道防线：`LRU` 防内存撑爆、`TTL` 防过期知识长期复用、`温度门控` 防高随机输出被缓存。
- 现在可以稳定观测缓存价值：命中率、miss 次数、淘汰次数、当前缓存大小。
- 首版缓存是“进程内内存缓存”，重启进程会丢失，这是当前阶段有意选择的 MVP 边界。

**阶段 2 实现说明（代码路径 / 函数 / 方法）**

- `src/generation_cache.py`
  - `GenerationCache.make_key(...)`：将 `query/context/model/temperature_bucket` 规范化后做 `sha256`，保证同输入同键。
  - `GenerationCache.get(key)`：先做过期检查，再命中返回并更新 LRU 顺序；未命中累加 `misses`。
  - `GenerationCache.set(key, value, temperature=...)`：先做温度阈值判断，再写入并设置 `expires_at`；超出容量触发 LRU 淘汰并累加 `evictions`。
  - `GenerationCache.stats()`：统一返回 `hits/misses/evictions/size`，用于后续报告和 notebook 展示。
  - `BaseCacheBackend` + `MemoryCacheBackend`：持久化后端扩展占位已预留；当前默认内存后端。
- `tests/test_generation_cache.py`
  - 覆盖四个关键场景：同输入同键、TTL 过期、高温不缓存、LRU 淘汰（当前 4 passed）。
- `notebooks/answer-eval-cache-batch.ipynb`
  - C2 演示 miss -> hit。
  - C3 演示 TTL 过期与高温不缓存。

### 阶段 3：批量处理（BatchRunner，optional） ✅

- [x] `ThreadPoolExecutor` 包装单 query 任务（cache + pipeline + eval）
- [x] `max_workers` 默认 `min(4, os.cpu_count() or 1)`
- [x] 单任务 `try/except`：失败项带 `error`，不拖垮整批
- [x] 输出顺序与输入 `queries` 一致
- [x] 单元测试：mock 慢任务 + 故意失败任务
- [x] Notebook C4：批量 4 query（并行）+ 失败任务容错演示
- [x] 固定并发原则：并行的是“多 query 之间”，单 query 内部阶段保持串行
- [x] 预留自适应并发占位：记录 `avg_latency` / `error_rate`，后续用于自动调参

**阶段 3 完成说明**

- 本阶段把“批量更快”落地了：可以同时处理多条 query，而不是一条跑完再跑下一条。
- 失败隔离已经生效：某一条任务异常不会中断整批，其它任务照常返回结果。
- 结果顺序做了对齐：即使并发执行，最终输出顺序仍与输入 query 顺序一致，便于后续评测对照。
- 增加了批量统计口径：可直接拿到平均耗时和错误率，为后续并发调优提供抓手。

**阶段 3 模型兼容性分析**

- 目前方案在“批量调度层”是**通用方案**，不是 Ollama 特化：
  - `BatchRunner.run_batch()` 只依赖 `task_fn(query)`，不关心底层是本地模型、云 API，还是其它推理后端。
- 当前特化点主要在“任务执行层”：
  - 若 `task_fn` 内部调用 08 的 `MedicalGenerationPipeline`，就会继承其本地 Ollama 依赖。
- 结论：本阶段已做到**调度通用、执行可替换**；后续接入其它模型时，优先替换 `task_fn/adapter`，不用重写并行框架。

**阶段 3 接口预留（已新增）**

- 新增 `src/model_adapter.py`：
  - `GenerationRequest` / `GenerationResponse`：统一请求与响应结构。
  - `ModelAdapter`（Protocol）：定义 `generate(request)` 标准接口。
  - `PipelineModelAdapter`：把现有 `pipeline.run(query)` 包装成标准接口，兼容当前实现并为未来多模型切换留钩子。
- 后续阶段建议：
  - 在 `pipeline_with_eval.py` 里优先依赖 `ModelAdapter`，而不是直接绑某个具体 pipeline。
  - 在缓存键中继续保留 `model/provider` 维度，避免跨模型误命中。

**阶段 3 实现说明（代码路径 / 函数 / 方法）**

- `src/batch_runner.py`
  - `BatchRunner.run_batch(queries, task_fn, max_workers=...)`：基于 `ThreadPoolExecutor` 并行调度；每个 query 独立执行，异常在单任务内捕获。
  - `BatchRunner._run_single(...)`：封装单条任务执行，统一返回 `status/latency/error` 字段。
  - `BatchRunner.summarize(results)`：汇总 `total/succeeded/failed/avg_latency/error_rate`，输出 `BatchStats`。
  - 并发默认值：`min(config.max_workers, min(4, os.cpu_count() or 1))`。
- `tests/test_batch_runner.py`
  - 覆盖三类关键行为：顺序对齐、失败隔离、统计结果正确（当前 3 passed）。
- `notebooks/answer-eval-cache-batch.ipynb`
  - C4 演示并发批量执行、单条失败不中断、统计字段输出。

### 阶段 4：流水线粘合（pipeline_with_eval） ✅

- [x] `run_with_cache_and_eval(query, *, use_cache=True, ground_truth_entry)`
- [x] 集成 08 `MedicalGenerationPipeline`
- [x] 集成 `ModelAdapter`（优先使用统一接口，兼容未来多模型）
- [x] 返回扩展结构：
  - [x] `generation`（08 原 result）
  - [x] `evaluation`（09 metrics）
  - [x] `cache`（`hit`, `key`, `stats`）
- [x] Notebook C5：端到端 `run_with_cache_and_eval` 复跑 08 四条 query，并展示汇总表
- [x] 固定输出契约（schema）落盘：`outputs/samples/eval_cache_batch_report.json`
- [x] 预留字段：`extensions`（后续放持久化缓存元数据、语义匹配附加分等）

**阶段 4 完成说明**

- 本阶段把“查答案 + 少重复写”真正串到一条统一接口里了：一次调用同时拿到生成结果、评估结果和缓存状态。
- 通过 `ModelAdapter` 把模型调用抽象出来，当前可继续用 08 流水线，后续换模型时不用重写评估和缓存逻辑。
- 缓存命中时可直接复用生成结果，未命中时再生成并回填缓存，随后统一执行评估，输出格式稳定可复用。
- 统一输出结构已经固定：`generation / evaluation / cache / extensions`，后续 CLI 与报告都可直接消费。

**阶段 4 实现说明（代码路径 / 函数 / 方法）**

- `src/pipeline_with_eval.py`
  - `PipelineWithEval.from_pipeline(...)`：将现有 pipeline 包装为 `PipelineModelAdapter`，兼容 08 流水线。
  - `run_with_cache_and_eval(...)`：主入口，执行“查缓存 -> 生成 -> 评估 -> 统一返回”。
  - `_run_generation(...)`：把 `GenerationRequest` 发送给 `ModelAdapter`，并归一化为标准 `generation` payload。
  - 缓存键由 `GenerationCache.make_key(query, context, model, temperature)` 生成，确保同输入可命中。
- `src/model_adapter.py`
  - 提供 `ModelAdapter` 协议及 `PipelineModelAdapter` 实现，完成“执行层可替换”。
- `tests/test_pipeline_with_eval.py`
  - 覆盖两类关键行为：miss->hit（验证缓存生效）与 `force_refresh`（验证可强制绕过缓存）。
- `notebooks/answer-eval-cache-batch.ipynb`
  - C5 演示统一输出结构与二次调用命中缓存。

### 阶段 5：Notebook 汇总导出与 CLI 对齐 ☐

- [ ] Notebook C6：导出 `eval_cache_batch_report.json` + 关键指标结论区
- [ ] Notebook 全量复核：检查 C0–C6 是否与各阶段代码一致
- [ ] `scripts/run_eval_cache_batch.py`：CLI 等价入口（参数与 notebook 对齐）
- [ ] 报告素材打包：导出“命中率、平均耗时、评估分数分布、失败样本”四类图表/表格

**阶段 5 完成说明（待填写）**

### 阶段 6：测试与交付 ☐

- [ ] `pytest tests/` 全绿（evaluator / cache / batch 可 mock Ollama）
- [ ] 用 08 固定 query 跑通：评估指标有值、第二次命中缓存、批量 4/4 返回
- [ ] 更新根目录 `README.md` 阶段 09 条目（完成后）
- [ ] （可选）`docs/答案评估与缓存报告.md`

**阶段 6 完成说明（待填写）**

---

## 验证用例（与 08 对齐）

| # | query | 验证点 |
|---|-------|--------|
| 1 | `What is the treatment for MI?` | ROUGE vs gt；关键信息 recall；幻觉信号 |
| 2 | `metformin cardiovascular effects` | 剂量/机制类短语提取 |
| 3 | `papers on malaria after 2015` | 时间范围正则；年份相关 gt |
| 4 | `warfarin atrial fibrillation elderly` | 安全信息（bleeding risk）信号 |

**缓存验证**：

| 场景 | 期望 |
|------|------|
| 同 query + 同 context + 低温 | 第二次 `cache.hit == True` |
| 提高 temperature | 不写入缓存或新 key |
| 等待 TTL 过期 | `get` 返回 `None`，重新生成 |
| 填满 `max_entries` | 最久未用条目被淘汰 |

**批量验证**：

| 场景 | 期望 |
|------|------|
| 4 条正常 query | 返回 4 条，顺序一致 |
| 注入 1 条非法/超时 query | 该条 `error`，其余成功 |

---

## 交付产物清单（预填）

| 产物 | 格式 | 路径 | Git |
|------|------|------|-----|
| 参考答案 | JSON | `data/ground_truth.json` | ✅ |
| 答案评估器 | Python | `src/answer_evaluator.py` | ✅ |
| 正则模式库 | Python | `src/patterns.py` | ✅ |
| 生成缓存 | Python | `src/generation_cache.py` | ✅ |
| 批量运行器 | Python | `src/batch_runner.py` | ✅ |
| 粘合流水线 | Python | `src/pipeline_with_eval.py` | ✅ |
| 演示 notebook | `.ipynb` | `notebooks/answer-eval-cache-batch.ipynb` | ✅ |
| CLI 脚本 | Python | `scripts/run_eval_cache_batch.py` | ✅ |
| 评测报告样例 | JSON | `outputs/samples/eval_cache_batch_report.json` | ✅ |
| 运行 log | JSON | `outputs/logs/eval_cache_batch_*.json` | ✅ |

---

## 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 无高质量 ground truth | ROUGE / recall 无意义 | 先为 4 条手写 `reference_answer` + `key_phrases` |
| Ollama 并发过高 | 超时或排队 | `max_workers` 限制为 2–4；批量可串行模式开关 |
| 缓存含过时医学结论 | 错误答案被复用 | TTL + 低温门控；`force_refresh=True` 绕过 |
| 幻觉规则误报 | 分数偏高 | 规则可配权重；与 critical_reviewer 输出交叉参考 |
| ROUGE 对结构化答案偏低 | 指标不好看 | 报告同时展示 key_info_recall 与幻觉分 |

---

## 本周执行顺序（建议）

1. **`ground_truth.json` + AnswerEvaluator（含单元测试）**  
2. **GenerationCache（miss/hit/TTL/温度门控）**  
3. **`pipeline_with_eval` 单条端到端**  
4. **BatchRunner + 复跑 08 四条 query**  
5. **阶段收尾：Notebook C6 导出 + CLI 对齐 + README / 报告**

---

## 报告撰写映射（实现后直接套用）

> 目标：写报告时“设计思路 ↔ 代码实现 ↔ 验证结果”一一对应，避免空泛描述。

| 报告章节建议 | 设计思路（本计划） | 代码落点（实现后填写） | 证据材料（notebook/outputs） |
|-------------|--------------------|------------------------|------------------------------|
| 评估器设计 | ROUGE + key_info_recall + 幻觉风险 + 可读性四维联合 | `src/answer_evaluator.py`、`src/patterns.py` | C1、`eval_cache_batch_report.json` |
| 缓存策略设计 | query+context 哈希；LRU+TTL+低温门控；时效优先 | `src/generation_cache.py` | C2/C3、缓存统计字段 |
| 批量处理设计 | 多 query 并行、单 query 串行、失败隔离、顺序对齐 | `src/batch_runner.py` | C4、批量结果对照表 |
| 粘合流水线设计 | 统一输出 `generation/evaluation/cache` | `src/pipeline_with_eval.py` | C5、端到端汇总 |
| 工程边界与扩展 | 本周采用内存缓存与规则分；预留持久化/语义匹配扩展 | `src/config.py`、占位接口 | C6、风险与后续计划 |

**报告写作硬规则（建议固定）：**

- [ ] 每节至少包含：设计目的、实现方法、关键参数、结果截图/表格、局限与下一步
- [ ] 所有“后续扩展”必须对应到本计划占位符（避免写成无落点愿景）
- [ ] 所有结论尽量给出可复现实验入口（notebook cell 或 CLI 命令）

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-07-07 | 创建阶段 09 `schedule.md`，对齐任务书与 08 测试 query，待启动实施 |
| 2026-07-07 | 阶段 0 完成：目录骨架、`requirements.txt`、`src/bootstrap.py`、`src/config.py`、`data/ground_truth.json`、notebook C0 初始化 |
| 2026-07-07 | 阶段 1 完成：`patterns.py` + `answer_evaluator.py` + `tests/test_answer_evaluator.py`（4 passed）+ notebook C1 |
| 2026-07-07 | 阶段 2 完成：`generation_cache.py`（LRU+TTL+温度门控+统计+后端占位）+ `tests/test_generation_cache.py`（4 passed）+ notebook C2/C3 |
| 2026-07-07 | 阶段 3 完成：`batch_runner.py`（并行+失败隔离+顺序对齐+统计）+ `tests/test_batch_runner.py`（3 passed）+ notebook C4 |
| 2026-07-07 | 阶段 4 完成：`pipeline_with_eval.py`（generation+cache+evaluation 统一接口）+ `model_adapter.py` 适配层 + `tests/test_pipeline_with_eval.py`（2 passed）+ notebook C5 |
