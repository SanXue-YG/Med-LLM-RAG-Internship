# （打包）LangChain_RAG · 02 打包计划（基于 01–12 已完成成果）

> **状态**：📋 规划（12 服务化完成后启动）  
> **日期**：2026-07-27  
> **前身**：[`01schedule.md`](01schedule.md) 为早期 LangChain 从零搭建草案，**多数能力已由阶段 01–11 以非 LangChain 主路径交付**；本文件改为 **产品打包 / 运行时组装** 计划。  
> **上游**：11 HTTP API · 12 会话/统计/文档 · Dataset 全量索引 · [`Dataset/打包资产清单.md`](../Dataset/打包资产清单.md)

---

## 1. 目标（一句话）

把已验证的医学 RAG（检索 → 约束生成 → FastAPI）打成 **可部署运行包**：数据卷 + 服务进程 + 配置，而不是再重写一套算法周。

---

## 2. 已完成、可直接消费的成果

| 能力 | 阶段 | 打包时怎么用 |
|------|------|--------------|
| 全量向量库 | 04 | 挂载 `Dataset/chroma/chroma_db_full` |
| 查询增强 + 多路检索 + 重排 | 05–06 | 进程内 pipeline；回查可改读 **`documents/full/*.sqlite`**（索引 ✅ 已建；代码切换待打包 P0） |
| 组装 / 生成 / 约束 | 07–08–10 | `ConstrainedGenerationPipeline` |
| 评估/缓存/BM25 分片 | 09 | BM25 挂载 `bm25_full`；缓存可选 |
| HTTP 问答 | 11 | `/qa` · `/qa/stream` · health/ready |
| 会话 / 统计 / 文档 API | 12（✅ 0–5 · 待阶段 6） | 文档读 `documents/full/documents_full.sqlite`；日常 API 入口为 12；全量仿真见 `run_full_ops_smoke` |

[`01schedule.md`](01schedule.md) 中「Chunking / Embedding / Chroma / Retriever / Prompt」等 **已由 03–10 落地**；打包阶段 **默认不重做**，除非明确要 LangChain 换皮。

---

## 3. 运行时数据清单（摘要）

详见 [`Dataset/打包资产清单.md`](../Dataset/打包资产清单.md)。

**建议进运行环境**：

1. `chroma_db_full`  
2. `bm25_full`  
3. ✅ `documents/full/documents_full.sqlite`（4,557,627 篇 · ~11.5 GB；逻辑分片单库 + progress 断点）  
4. Ollama 模型或远端 LLM 配置  
5. 应用代码（11+12）+ `.env`

**可外置**：`oa_comm_slim.jsonl`、`oa_comm_chunks.jsonl`（重建用；documents 全量写入 `documents/full/`，可 overnight + resume）。

语料增补 / schema 升级：[`（未来优化）打包后数据更新/schedule.md`](../（未来优化）打包后数据更新/schedule.md)（文档侧：upsert 补丁；勿与 BM25 物理分片混为一谈）。

---

## 4. 分阶段（打包工程自身）

### P0：资产齐套与路径 ☐

- [x] 确认 Dataset 全量 Chroma / BM25 / **documents_full** 存在且 count 合理（documents：**4,557,627** · manifest completed）  
- [ ] `dataset_paths` + 环境变量文档化  
- [ ] 06 回查切换到 documents sqlite（或双读：sqlite 优先，slim 回退）

### P1：单容器 / 单机进程编排 ☐

- [ ] Dockerfile 或 compose：API 服务 + （可选）Ollama 侧车  
- [ ] 数据 **volume 挂载**（勿把 70GB 打进镜像层）  
- [ ] `MED_RAG_RETRIEVAL_MODE=full` 启动烟测：`/health` `/ready` `/qa` `/documents/{id}`

### P2：配置与密钥 ☐

- [ ] `.env.example`（HOST/PORT/模式/模型名/Dataset 根）  
- [ ] 鉴权是否启用（11 预留 2001；打包时可接简单 API Key）

### P3：文档与验收 ☐

- [ ] 部署 runbook（从 [`12 .../docs/部署与API调用说明.md`](../12%20服务化与接口开发第二部分/docs/) 升级）  
- [ ] 验收表：样本烟测 + 全量 1–2 query  
- [ ] 数据更新指向 [`（未来优化）打包后数据更新/schedule.md`](../（未来优化）打包后数据更新/schedule.md)

### P4：（可选）LangChain 外壳 ☐

- [ ] 仅当产品要求 LC 生态时：用 LC 包一层现有 retriever/generator，**不替换**已验收管线  
- [ ] 否则保持 FastAPI 直挂 10/11/12

---

## 5. 非目标（本打包计划不做）

- 重跑 02–04 全量解析/嵌入（除非损坏重建）  
- 前端 UI（另项）  
- K8s 生产编排（可后续）

---

## 6. 进度记录

| 日期 | 事项 |
|------|------|
| 2026-07-27 | 创建 02schedule：从「重做 RAG」改为「基于 01–12 打包」；对齐全库文档索引与数据清单 |
| 2026-07-27 | 对齐 documents **逻辑分片**建库（断点续建）；运行时仍挂载单库 sqlite |
| 2026-07-27 | **documents/full 已建成**：4,557,627 篇 · ~11.5 GB · manifest completed；P0 资产自检可勾 documents |
