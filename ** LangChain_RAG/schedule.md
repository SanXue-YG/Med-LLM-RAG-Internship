# 02 LangChain_RAG · 总体规划

> **本工程目标**：在 [01 验证模型](../01%20验证模型/) 已经验证好的本地 LLM 与依赖环境上，搭建一套医学专业知识 RAG 系统。
>
> **演进方式**：**逐步分析、逐步实现**。本文件只列「阶段骨架 + 待讨论决策点」，不预先写死具体参数、字段、矩阵；每个阶段开工前对齐细节再动手。
>
> **本工程边界（初稿，可调整）**：
> - 数据：复用 01 阶段产出的 PMC 文献样本 `data/processed/sample.jsonl`
> - 框架：LangChain + Chroma（任务文档要求）
> - 推理：本地 Ollama 为主；可选「智增增 API」做横向对照（详见 0.1）

---

## 0. 总体路线（一图概览）

```
[01 验证模型 产物: sample.jsonl]
            │
            ▼
   ①  Chunking          ← 切块策略待定
            │
            ▼
   ②  Embedding         ← 模型与设备策略待定
            │
            ▼
   ③  Chroma 向量库     ← 持久化到 chroma_db/
            │
            ▼
   ④  Retriever         ← 检索策略待定
            │
            ▼
   ⑤  Prompt + LCEL chain
            │
            ▼
   ⑥  LLM (Ollama / 智增增 二选一或并存)
            │
            ▼
   ⑦  评测（可选；具体怎么做开工再设计）
```

---

## 0.1 与 `benchmark_batch.py` 的关系（**仅复用方法 + Key**）

`benchmark_batch.py` 是你之前做"图片解题"的工程，**在本工程里只复用两点**：

| 复用项 | 在哪里用 |
|---|---|
| `ChatOpenAI(model=..., api_key=ZZZ_API_KEY, base_url=ZZZ_BASE_URL, ...)` 调用智增增的方式 | 阶段 5 接 LLM 时，作为「云端模型」入口 |
| 智增增的 `ZZZ_API_KEY` / `ZZZ_BASE_URL` 等 Key 配置 | 通过 `.env` 注入，避免硬编码 |

**不直接复用**：
- 双链路 A/B 设计、JSONL 字段、artifacts 目录命名、`build_llm()` 具体签名、模型矩阵 ……
- 这些都根据本工程实际需求重新设计；当真要做评测时另起讨论。

**未来的扩展方向（不在本规划锁死）**：
- 智增增封装 `ChatOpenAI` 走 OpenAI 兼容协议；本地 Ollama 走 `ChatOllama`
- 之后如果要做对比，可能会想把这两种 provider 抽象到一个统一调用入口；但**具体接口由那时的需求决定**，不提前过度设计。

---

## 0.2 决策记录（开工时逐步填，**当前都是候选**）

| 项 | 候选 | 是否已决 | 备注 |
|---|---|---|---|
| 切块策略 | RecursiveCharacterTextSplitter / 按段落 / 按句子 / 其他 | ❌ 待阶段 2 讨论 | |
| chunk_size / overlap | 512+64 / 800+80 / 1024+128 / 其他 | ❌ 待阶段 2 讨论 | |
| Embedding 模型 | bge-base-en / MiniLM / 医学专用 / 其他 | ❌ 待阶段 3 讨论 | PMC 是英文 |
| Embedding 设备 | MPS / CPU | ❌ 待阶段 3 讨论 | M3 支持 MPS |
| 向量库 | **Chroma**（任务文档要求） | ✅ | 持久化到 `chroma_db/` |
| Retriever | vector / mmr / hybrid / 其他 | ❌ 待阶段 4 讨论 | |
| LLM Provider | 本地 Ollama / 智增增 / 两者 | ❌ 待阶段 5 讨论 | 主用本地，云端做对照可选 |
| Prompt 模板 | 自由设计 | ❌ 待阶段 5 讨论 | 必须强约束"基于检索内容" |
| 是否做多模型评测 | 是 / 否 | ❌ 待阶段 6 讨论 | 老师建议做，具体范围开工讨论 |
| 评测指标 | — | ❌ 待阶段 6 讨论 | 决定做评测后再设计 |

---

## 0.3 目录约定（沿用 01 验证模型 的"工程容器化"经验）

```text
02 LangChain_RAG/
├── 任务.txt                       ← 阶段开始时补充
├── schedule.md                    ← 本文件（实时滚动更新）
├── requirements.txt
├── main.ipynb                     ← 与 01 同款的总入口 notebook
├── start_jupyter.sh               ← 拷自 01，仅改 PROJECT 路径
├── start_ollama.sh                ← 拷自 01
├── .env                           ← 智增增 Key 等敏感配置（git ignore）
├── caches/                        ← HF / Torch / Transformers 缓存重定向
├── ollama_models/                 ← 与 01 共用（软链接，避免重复占盘）
├── data/                          ← 中间产物
├── chroma_db/                     ← Chroma 持久化
├── outputs/                       ← 评测产物（具体子结构开工时设计）
└── src/                           ← 可选：Python 模块化
```

> 与 01 的差异：**新增 `.env`**（智增增 Key 走环境变量，不再硬编码）。

---

## 阶段 1：工程容器化（约 1h）

> 这一步几乎是从 01 复制改路径，**风险最低，先做**。

- [ ] 拷 `01 验证模型/start_jupyter.sh` → 本目录，改 `SCRIPT_DIR` 自适应
- [ ] 拷 `01 验证模型/start_ollama.sh` → 本目录
- [ ] `ollama_models/` 软链接到 01 的目录（避免重复占盘）
- [ ] 创建独立 conda 环境 `med-rag-build`，注册 ipykernel
- [ ] 安装 LangChain 生态新依赖（具体清单开工时确认）
- [ ] 创建 `.env`，填入智增增 Key + base_url + 模型名占位
- [ ] 启动 Jupyter / Ollama，跑通最小 import 测试

**待讨论**：是否复用 01 的 conda 环境 `med-rag-verify`？还是新建？

---

## 阶段 2：文档切块（Chunking）

**目标**：把 `sample.jsonl` 切成可以 embed 的 chunks。

**输入**：`../01 验证模型/data/processed/sample.jsonl`
**产出**：`data/chunks/chunks.jsonl`（具体 schema 开工时定）

**待讨论**：
- 切哪几个字段？（abstract / body / 二者合并？）
- 用什么 splitter？参数怎么定？
- 元数据保留哪些字段？

---

## 阶段 3：Embedding 流水线

**目标**：把 chunks 编码成向量。

**输入**：阶段 2 的 chunks
**产出**：向量数组 + 对应元数据

**待讨论**：
- 选哪个 embedding 模型？（医学语料适配？开源还是 API？）
- 设备：MPS / CPU？
- 批 size、是否 normalize、是否多语言

---

## 阶段 4：Chroma 入库 + 检索接口

**目标**：能根据问题检索到相关 chunks。

**输入**：阶段 3 的向量 + 元数据
**产出**：持久化的 Chroma collection + 一个简单的 `retrieve(query, k)` 函数

**待讨论**：
- collection 命名规范
- 检索接口签名与返回结构
- 是否预先做几个 retriever 策略对照（vector / mmr / ...）

---

## 阶段 5：RAG 链路串联（LangChain LCEL）

**目标**：跑通端到端：问题 → 检索 → 拼上下文 → 调 LLM → 输出答案。

**输入**：阶段 4 的检索接口
**产出**：一个可调用的 RAG chain；至少能用本地 Ollama 跑出合理答案。

**待讨论**：
- Prompt 模板设计（系统提示 / 检索内容注入格式 / 拒答约束）
- LLM 用哪一个？（本地 Ollama / 智增增 / 都试）
- **智增增接入**：参照 `benchmark_batch.py` 里 `ChatOpenAI(...)` 的写法；具体封装方式当时讨论
- 是否支持 streaming 输出
- 长上下文怎么处理（chunk 数量上限、超长截断策略）

---

## 阶段 6：评测（可选，决定后再细化）

**问题**：要不要做多模型 / 多策略横向对比？

**如果要做**，开工前需要回答：
- 评测什么？（答案准确性 / 检索质量 / 延迟 / token 用量 / 拒答能力 ...）
- 对比哪些维度？（模型 × 检索策略 × Prompt 变体 ...）
- 评测数据从哪来？（人工出题 / GPT 出题 / 公开医学问答数据集）
- 答案怎么打分？（LLM-as-judge / 人工 / 关键词匹配）
- 怎么记录与展示结果？

> **这一阶段如何设计，留到阶段 5 跑通后再具体讨论**，避免提前过度设计。

---

## 阶段 7：交付与归档

- [ ] 整理 `main.ipynb`：从头到尾一键复现
- [ ] 写一份简短 `README.md`：启动方式 + 关键发现
- [ ] 更新 `requirements.txt`
- [ ] 整体备份准备（与 01 类似的容器化清单）

---

## 工作方式约定

1. **每个阶段开工前对齐**：本文件 §决策记录里对应行从 ❌ 改成具体方案，然后再写代码
2. **不照搬历史项目设计**：`benchmark_batch.py` 只作为「智增增调用方式 + Key」的参考，其他从需求出发
3. **小步快跑**：每个阶段先跑通最小可用版本，再迭代细化
4. **变更记录**：本文件 §进度记录 节追加 Day N 小结，与 01 风格一致

---

## 风险与备选

| 风险 | 应对（待具体化） |
|---|---|
| Mac 16GB 跑 embedding + LLM 内存吃紧 | 阶段 3/5 测试时再调 batch 与上下文 |
| Chroma 在 macOS 偶发 SQLite 问题 | 备选 FAISS（同 LangChain 接口） |
| 智增增 API 偶发 429/超时 | 决定接入后再细化重试与计时策略 |
| PMC 100 篇知识覆盖窄 | 评测问题刻意控制在样本可覆盖范围；超出范围用于拒答测试 |

---

## 进度记录

> 滚动更新，每个阶段收尾追加一段小结。

- [ ] 阶段 1 工程容器化
- [ ] 阶段 2 切块
- [ ] 阶段 3 Embedding
- [ ] 阶段 4 Chroma 入库 + 检索
- [ ] 阶段 5 RAG 链路
- [ ] 阶段 6 评测（决定做后再细化）
- [ ] 阶段 7 交付
