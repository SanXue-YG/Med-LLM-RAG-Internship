# 05 检索系统开发第一部分 — 执行计划

> **状态：✅ 查询理解与增强已完成**（2026-06-08）
>
> **本阶段范围（任务书）**：仅完成 **查询理解与增强** 模块代码；**不包含** 混合检索、重排序、LLM 生成答案（属后续 RAG 阶段）。
>
> **上游依赖**：04 阶段全量 ChromaDB（`pmc_oa_comm_full`，610 万条，`BAAI/bge-small-en-v1.5`）已就绪；本阶段先产出「增强后的查询对象」，再与 04 的 `ChromaIndexBuilder.query()` 对接。

---

## 任务书目标对照

| 任务书要求 | 本阶段交付 |
|------------|------------|
| 输入：用户自然语言查询 | `MedicalQueryEnhancer.process(query: str) -> EnhancedQuery` |
| 医学缩写 / 同义词 / 专业术语增强 | 静态词典 + 正则实体模式（任务书示例结构） |
| 生成向量查询 + 关键词查询 | `EnhancedQuery.vector_query`、`keyword_query` |
| BGE 向量检索查询（加指令前缀） | **复用 04 `DocumentEmbedder.encode_queries` 的指令**，勿自造前缀 |
| 提取过滤条件（时间范围等） | `EnhancedQuery.filters`（结构化 dict） |
| **本周产出** | 查询理解与增强 **代码 + 演示 notebook + 单元测试样例** |

---

## 与第四阶段的衔接

### 04 阶段可直接复用

| 资源 | 路径 | 本阶段用途 |
|------|------|------------|
| 嵌入模型封装 | `04 .../src/embedder.py` → `DocumentEmbedder` | 向量查询端 BGE 指令与编码（与建库模型一致） |
| 索引查询接口 | `04 .../src/index_builder.py` → `ChromaIndexBuilder.query()` | **可选** smoke test：验证 `vector_query` 能检索 |
| 全量向量库 | `D:\谷歌\04 向量化与索引构建\data\chroma_db_full\` | 联调时使用（非本周必跑全库） |
| 验证样本向量库 | 重跑 `vectorize-index.ipynb` → `data/chroma_db/` | 开发期优先用 1,267 条样本库联调 |
| 索引 metadata | `doc_id, chunk_index, total_chunks, source_title, token_count, strategy` | 见下方「过滤条件限制」 |

### 数据流（本阶段）

```
用户自然语言查询（中/英）
    ↓ 基础清洗（空白、标点、大小写策略）
    ↓ 医学实体识别（MEDICAL_PATTERNS：drug / disease / …）
    ↓ 缩写识别 + 静态同义词扩展（MEDICAL_SYNONYMS）
    ↓ 生成多版本查询
        ├─ vector_query  → 供 BGE/Chroma 语义检索（04 embedder 加指令）
        └─ keyword_query → 供后续 BM25/关键词检索（本阶段仅生成字符串）
    ↓ 提取 filters（年份范围、strategy 等）
EnhancedQuery 对象
    ↓ （可选联调）ChromaIndexBuilder.query(vector_query, where_filter=filters)
参考文档候选列表（后续阶段再做融合与排序）
```

### ⚠️ 已知约束（计划内说明，避免过度承诺）

| 约束 | 说明 | 本阶段处理 |
|------|------|------------|
| **语料为英文 PMC** | chunk 为英文 title+abstract | ✅ 与老师「英文优先」一致；中文增强 TODO |
| **索引无 pub_year** | 02 解析有 `pub_year`，但 03/04 chunk **未写入** Chroma metadata | `filters` 可**从查询中解析**年份意图；**暂无法**在全库 metadata 上过滤发表年（记录为后续增强项） |
| **BGE 指令措辞** | 任务书写 `Represent this question...`；04 建库用 `Represent this sentence...` | **必须与 04 一致**（`embedder.BGE_QUERY_INSTRUCTION`），否则向量空间不对齐 |
| **UMLS / MeSH** | 任务书提及可从标准术语库构建 | 本周用**静态小词典**即可；扩展留后续 |

---

## 已确认 / 建议决策（启动前）

| 决策项 | 建议 | 理由 |
|--------|------|------|
| 嵌入模型 | **`BAAI/bge-small-en-v1.5`**（与 04 相同） | 向量检索须与建库模型一致 |
| 词典规模 | 任务书示例 + **20~50 组**常见缩写/同义词 | 满足演示与测试，可 JSON 外置便于扩展 |
| 实体类型 | `drug`、`disease`、`abbrev`（首版） | 对齐任务书 `MEDICAL_PATTERNS` 思路 |
| 开发验证库 | 优先 **04 样本库**（1,267 条） | 秒级联调；全量库仅最终 smoke test |
| 代码复用 | `sys.path` 引用 `04 .../src`，**不复制** embedder | 避免双份模型逻辑分叉 |
| 本阶段边界 | **不实现** 混合检索融合、重排序、答案生成 | 任务书本周仅「查询理解与增强代码」 |
| **查询语言（老师已确认）** | ✅ **优先英文**；中文增强视剩余开发时间再添加 | PMC 语料为英文；与 BGE-small-en 一致 |

---

## 模块设计

### 目录结构（规划）

```
05 检索系统开发第一部分/
├── 任务.txt
├── schedule.md                  # 本文件
├── requirements.txt             # 复用 med-rag-verify；本阶段新增依赖极少
├── data/
│   └── medical_synonyms.json    # 静态同义词 / 缩写表（可 git）
├── src/
│   ├── __init__.py
│   ├── medical_patterns.py      # MEDICAL_PATTERNS 正则 + 实体类型枚举
│   ├── query_enhancer.py        # 核心：MedicalQueryEnhancer
│   └── models.py                # EnhancedQuery dataclass / TypedDict
├── notebooks/
│   └── query-enhancement.ipynb  # 演示：样例查询 → 增强结果 →（可选）Chroma 检索
├── tests/
│   └── test_query_enhancer.py   # 或 notebook 内 assert 块
└── outputs/
    └── samples/
        └── enhancement_examples.json   # 固定查询的增强输出快照
```

### 核心 API（草案）

```python
@dataclass
class EnhancedQuery:
    original: str              # 原始用户查询
    cleaned: str               # 清洗后文本
    entities: list[dict]       # [{type, text, span}, ...]
    expanded_terms: list[str]  # 同义词 / 全称扩展项
    vector_query: str          # 供 encode_queries 的文本（已含 BGE 指令或 raw，见实现约定）
    keyword_query: str         # 空格分词 + 扩展词，供后续 BM25
    filters: dict                # 如 {"year_gte": 2015, "strategy": "sliding_window"}
    metadata: dict             # 调试信息：命中词典键、是否含中文等


class MedicalQueryEnhancer:
    def __init__(
        self,
        synonyms_path: str | Path | None = None,
        embedder: DocumentEmbedder | None = None,  # 可选，用于生成 vector embedding 预览
    ): ...

    def process(self, query: str) -> EnhancedQuery: ...
```

**处理流水线（对齐任务书伪代码）**

1. **基础清洗**：strip、合并空白、可选保留中文；英文术语统一小写（ drug 名大小写敏感处用白名单）
2. **识别医学实体**：对 `MEDICAL_PATTERNS` 各类型做 `\b...\b` 正则匹配
3. **同义词扩展**：查 `MEDICAL_SYNONYMS`（含任务书 `mi` → myocardial infarction 等）
4. **生成查询版本**
   - `vector_query`：清洗后的自然语言问句（**不加**指令前缀的 raw 文本交给 `DocumentEmbedder.encode_queries`；或文档化「前缀由 embedder 统一添加」）
   - `keyword_query`：实体 + 扩展词 + 剩余 token，去停用词（轻量英文 stoplist）
5. **提取过滤条件**
   - 年份：`after 2010` / `2015-2020` / `近5年` 等规则（中文规则可选）
   - metadata：`strategy=sliding_window` 等可从查询意图映射（显式关键词触发）
   - 记录 **无法作用于当前索引** 的 filter（如 `year_*`）到 `metadata` 供报告说明

### 静态资源配置（首版内容方向）

**`MEDICAL_SYNONYMS`（示例，写入 JSON）**

| 缩写/别名 | 扩展 |
|-----------|------|
| `mi` | myocardial infarction, heart attack |
| `hf` | heart failure |
| `dm` / `t2dm` | diabetes mellitus, type 2 diabetes |
| `metformin` | （药物名，可映射 MeSH 同义） |
| `cad` | coronary artery disease |
| `htn` | hypertension |

**`MEDICAL_PATTERNS`（示例）**

| 类型 | 模式示例 |
|------|----------|
| `drug` | metformin, aspirin, insulin, atorvastatin, warfarin, … |
| `disease` | diabetes, hypertension, malaria, cardiovascular, … |
| `abbrev` | 独立 `\b[a-z]{2,5}\b` + 词典反查（避免误扩） |

---

## 执行步骤

### 阶段 0：环境与目录 ✅

- [x] 创建 `src/`、`data/`、`notebooks/`、`outputs/samples/`、`tests/`
- [x] 编写 `requirements.txt`（复用 `med-rag-verify`）
- [x] 路径：`PERSIST_SAMPLE` / `PERSIST_FULL`（notebook C0）
- [x] 引用 04 `DocumentEmbedder` / `ChromaIndexBuilder`（`sys.path`）

### 阶段 1：静态资源与实体识别 ✅

- [x] `data/medical_synonyms.json`
- [x] `medical_patterns.py` + `extract_entities()`
- [x] `tests/test_query_enhancer.py`

### 阶段 2：查询增强核心 ✅

- [x] `models.py`：`EnhancedQuery` / `FilterItem`
- [x] `query_enhancer.py`：`MedicalQueryEnhancer.process()`
  - [x] 基础清洗、实体识别、同义词扩展
  - [x] `vector_query` / `keyword_query` 生成
  - [x] `filters` 提取（strategy 可执行；year/journal 解析 + `executable=false`）
- [x] 嵌入模型标注：`BAAI/bge-small-en-v1.5`（`metadata` + 模块注释）

### 阶段 3：演示与双库联调 ✅

- [x] `notebooks/query-enhancement.ipynb`（C0–C5，2026-06-08 跑通）
- [x] `outputs/samples/enhancement_examples.json`（4 条英文固定用例）
- [x] `outputs/samples/chroma_smoke_compare.json`（样本库 + 全量库对比）
- [x] `scripts/run_dual_smoke.py`（CLI 等价脚本）

### 阶段 4：文档与交付 ✅

- [x] 更新根目录 `README.md` 阶段 05 条目
- [x] 本 `schedule.md` 进度与验证结果
- [x] `笔记/05笔记·.md` 补充 notebook 实测（Q11）

---

## 验证用例（建议固定）

| # | 输入查询 | 期望增强行为 |
|---|----------|--------------|
| 1 | `What is the treatment for MI?` | 识别 `MI` → 扩展 myocardial infarction；`keyword_query` 含扩展词 |
| 2 | `metformin cardiovascular effects` | 识别 drug `metformin`；vector/keyword 均保留核心语义 |
| 3 | `metformin effects on cardiovascular disease` | 识别 drug；英文主路径 |
| 4 | `papers on malaria after 2015` | `filters.year_gte=2015`，**executable=false** |
| 5 | `circadian rhythm in sliding window chunks` | 若规则匹配 → `strategy=sliding_window`，**executable=true** |
| 6 | `   ` / 超长重复词 | 边界：空查询；超长截断 |
| （可选 TODO） | 中文 query | 检测 CJK 提示「请用英文」；非本周必测 |

---

## 交付产物清单

| 产物 | 格式 | 路径 | Git |
|------|------|------|-----|
| 静态医学同义词表 | JSON | `data/medical_synonyms.json` | ✅ |
| 查询增强模块 | Python | `src/query_enhancer.py` 等 | ✅ |
| 演示 notebook | `.ipynb` | `notebooks/query-enhancement.ipynb` | ✅ |
| 增强样例输出 | JSON | `outputs/samples/enhancement_examples.json` | ✅ |
| 双库 smoke 对比 | JSON | `outputs/samples/chroma_smoke_compare.json` | ✅ |
| Chroma 联调脚本 | Python | `scripts/run_dual_smoke.py` | ✅ |
| 向量库 | ChromaDB | 04 阶段已有 | ❌ |

---

## 预估工作量

| 项目 | 预估 |
|------|------|
| 目录 + 静态词典 | 1–2 h |
| 实体识别 + 同义词扩展 | 2–3 h |
| EnhancedQuery + filters | 1–2 h |
| Notebook 演示 + 样例 JSON | 1 h |
| 可选 Chroma 联调 | 0.5–1 h |
| **合计** | **约 1 个工作日** |

---

## 风险与应对

| 风险 | 应对 |
|------|------|
| 中文 query | ✅ 老师确认英文优先；检测 CJK 可提示，非本周必做 |
| 缩写误扩展（如 `in`→?） | 缩写表**白名单** + 单词边界；仅扩展词典内键 |
| 与 04 BGE 指令不一致 | `vector_query` 只传 raw 文本，**统一走** `DocumentEmbedder.encode_queries()` |
| 时间过滤无法作用于索引 | `filters` 仍解析并写入结果；文档注明需后续补 `pub_year` metadata 或后过滤 |
| 任务书示例与 PMC 领域 | 词典覆盖心血管/代谢/common OA 术语；随 RAG 反馈迭代 |

---

## 已确认事项（老师回复）

| 项 | 结论 | 对本阶段实现的影响 |
|----|------|-------------------|
| **查询语言** | ✅ **先优先英文**；中文视剩余时间再加 | 词典、patterns、测试用例均为英文 |
| **时间过滤 / 重建索引** | ✅ **现阶段不重建**；filter 解析为主，年份类 `executable=false` | 见「过滤条件决策」、05 笔记 Q9 |

### 过滤条件决策（老师未单列回复时的工程结论）

| 判断 | 依据 |
|------|------|
| **不必为时间 filter 重建向量库** | 老师仅强调英文优先，**未要求**补 `pub_year` 或 3 天级返工；05 本周交付为**增强代码**，非新索引 |
| **任务书「提取过滤条件」仍要做** | 从英文 query **解析**用户意图（含 `after 2015` 等），写入 `EnhancedQuery.filters` |
| **索引层可执行的 filter** | `strategy`、`doc_id` 等现有 metadata（04 已验证 `strategy`） |
| **解析但暂不执行的 filter** | `year_gte` / `year_lte` / `journal` → `executable: false`，留待 RAG 阶段用 文本块数据集 slim JSONL **检索后过滤** |
| **若日后必须「索引内筛年份」** | 再单独立项：chunk metadata 补 `pub_year` 或重建（非 05 本周范围） |

```text
用户 query ──→ 05 解析 filters
                    ├─ executable=true  → 传给 Chroma where / post-filter（strategy 等）
                    └─ executable=false → 仅记录在 EnhancedQuery；RAG 阶段再后过滤
```

## 待确认 / 自行决定（不影响交付物类型）

| 项 | 结论 |
|----|------|
| **本周联调 Chroma** | ✅ 样本库 smoke test（验证 05→04 路径） |
| **filters 范围** | ✅ 解析 strategy + year + 简单 doc 意图；year/journal **不执行** |
| **词典维护** | ✅ JSON 外置 + 代码 patterns |

---

## 下一步行动（当前执行顺序）

> **目标**：交付英文 query 增强模块；**不**重建 Chroma / JSONL；filter 解析与可执行性分离。

### Step 1：搭建骨架（阶段 0）✅

### Step 2：静态资源（阶段 1）✅

### Step 3：核心增强（阶段 2）✅

### Step 4：验证与双库联调（阶段 3）✅

- [x] `notebooks/query-enhancement.ipynb`（C0–C5，2026-06-08 Jupyter 跑通）
- [x] CLI `scripts/run_dual_smoke.py` 已跑通对比
- [x] `outputs/samples/enhancement_examples.json`
- [x] `outputs/samples/chroma_smoke_compare.json`

### Step 5：收尾（阶段 4）✅

- [x] schedule 进度勾选；README 增加 05 条目
- [x] **明确不做**：全量库压测、metadata 补 pub_year、中文翻译链

### 双库 smoke test（C3–C5，对比 HNSW bin 与耗时）

| 库 | 路径 | collection | 条数 | 用途 |
|----|------|------------|------|------|
| **样本** | `04.../data/chroma_db/` | `pmc_oa_comm_sample` | 1,267 | 快速验证 05→04 路径；通常含完整 HNSW bin |
| **全量** | `04.../data/chroma_db_full/` | `pmc_oa_comm_full` | 6,107,296 | 抽样 query 计时；当前多无 bin，观察 attach/query 行为 |

**入口**：`notebooks/query-enhancement.ipynb` C3–C5

| 步骤 | 内容 |
|------|------|
| attach 前 | 默认 **不** repair（保留样本库 bin）；仅 hnsw 报错时 `REPAIR_HNSW=True` |
| 探测 | `chroma_smoke.detect_hnsw_bins()` → 是否有 `data_level0.bin` 等 |
| 检索 | `ChromaIndexBuilder.query(enhanced.vector_query, where_filter=enhanced.chroma_where())` |
| 对比 | 同一 `SMOKE_QUERY` 各跑 3 次 `timed_queries()`，写入 `outputs/samples/chroma_smoke_compare.json` |

> **注意**：两库规模差 4800 倍，耗时差异主要来自**数据量**，bin 影响需结合 `hnsw.any_complete_hnsw` 与同等规模库对比解读。

### 双库 smoke 实测结果（2026-06-08，notebook C3–C5）

**统一 smoke query**：`metformin cardiovascular effects`（Top-5）

| 库 | 条数 | 完整 HNSW bin | 平均 query 耗时 | 备注 |
|----|------|---------------|-----------------|------|
| `chroma_db`（样本） | 1,267 | ✅ | **12.1 ms** | 带 `strategy=sliding_window` 过滤；Chroma `where=` 失败 → post-filter（与 04 一致） |
| `chroma_db_full`（全量） | 6,107,296 | ❌ | **16.2 ms** | 无 where 过滤 |

**增强模块验证（C1，4 条英文 query）**

| 查询 | 关键结果 |
|------|----------|
| `What is the treatment for MI?` | 扩展 myocardial infarction / heart attack |
| `metformin cardiovascular effects` | 识别 drug + disease 实体 |
| `papers on malaria after 2015` | `year_gte=2015`，**executable=false** |
| `circadian rhythm in sliding window chunks` | `strategy=sliding_window`，**executable=true** |

**结论（粗对比）**：全量库无 bin 仍可正常 query；本次同 query 下全量仅比样本慢约 1.3×，**不能**单独归因于 bin（规模差 4800 倍）。详见 `chroma_smoke_compare.json` 与笔记 Q11。

---

## GitHub 上传说明

| 纳入 Git | 不纳入 Git |
|----------|------------|
| `src/`、`data/medical_synonyms.json`、`notebooks/`、`tests/`、`scripts/run_dual_smoke.py` | 04 的 `chroma_db*` 目录 |
| `outputs/samples/*.json`、`schedule.md`、`requirements.txt` | 向量库与大型数据 |

---

## 进度记录

| 日期 | 事项 |
|------|------|
| 2026-06-02 | 阅读任务书，制定第五阶段执行计划（本文件） |
| 2026-06-02 | **老师确认**：查询增强 **优先英文**；中文功能视剩余开发时间再添加 |
| 2026-06-02 | **过滤条件决策**：不重建 03/04 库；filter 解析为主，year/journal 暂不执行；开始 Step 1 实施 |
| 2026-06-02 | 04 `vectorize-index.ipynb` 修复并跑通；05 代码骨架 + 双库 smoke test notebook |
| 2026-06-08 | **`query-enhancement.ipynb` C0–C5 跑通**；导出 `enhancement_examples.json`、`chroma_smoke_compare.json` |
| 2026-06-08 | 更新 `schedule.md`、根目录 `README.md`、`笔记/05笔记·.md`，准备 GitHub 上传 |

---

## 后续阶段预览（非本周）

| 阶段 | 内容 |
|------|------|
| 检索系统开发第二部分（推测） | 向量 + 关键词混合检索、分数融合、Top-K 候选 |
| LangChain RAG | 检索结果 → Prompt → 本地 LLM 生成答案 |
| 索引增强 | chunk metadata 增加 `pub_year`；或检索后按 XML/JSONL 二次过滤 |
