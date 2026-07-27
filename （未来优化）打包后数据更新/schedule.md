# （未来优化）打包后数据更新 — 计划

> **状态**：📋 规划（尚未实施）  
> **日期**：2026-07-27  
> **目标**：产品已打包运行后，若 PMC 语料增补或字段升级，如何 **打补丁** 或 **重建** Dataset，避免每次从零拷贝 70GB+。  
> **关联**：[`Dataset/打包资产清单.md`](../Dataset/打包资产清单.md) · [`Dataset/documents/README.md`](../Dataset/documents/README.md) · [`（打包）LangChain_RAG/02schedule.md`](../（打包）LangChain_RAG/02schedule.md)

---

## 1. 会变的数据 vs 相对稳定的代码

| 层 | 内容 | 更新频率 |
|----|------|----------|
| 检索索引 | Chroma / BM25 | 新文献入库时 |
| 篇级索引 | `documents/{sample,full}/documents_*.sqlite` | 新文献或元数据修订时（full ✅ 基线 4,557,627 篇 · 2026-07-27） |
| 原料 | slim / chunks JSONL | 上游解析流水线产出时 |
| 应用 | 11/12 FastAPI、10 约束管线 | 发版 |

本目录只规划 **数据侧** 更新；应用发版另走代码 CI。

---

## 2. 两种策略

### A. 增量补丁（优先）

适用：新增一批 pmcid，或少量字段回填。

```text
1. 得到增量 slim 行（或全 slim 中「未在 sqlite 出现的 pmcid」）
2. documents：与全量构建同一 upsert 内核，按批 INSERT OR REPLACE
     → `documents/full/documents_full.sqlite`；更新 manifest_full.row_count / updated_at
     → 另写 patch_manifest.json（pmcids 数、时间、schema_version、source）
3. chunks：仅对新文献跑 03 策略 → 增量 chunks
4. Chroma：add 新 chunk 向量（勿盲目全库重建）
5. BM25：或重建受影响分片 / 或标记「待全量重建」（分片 BM25 增量较难，可先接受定期全量）
```

**文档索引补丁相对容易**（SQLite 按主键 upsert；与「逻辑分片」批提交同一路径）。  
大补丁也可 `--batch-size` + 自己的 `progress.json`（按增量文件行号），避免一夜补丁中断白跑。  
**BM25 分片增量较难** → 短期可「文档+Chroma 增量，BM25 定期全量」。

### B. 全量重建（保底）

适用：分割策略变更、嵌入模型更换、schema 不兼容、索引损坏。

```text
1. 备份旧 Dataset（或 E:）
2. 用现行脚本重跑：slim→chunks→Chroma→BM25→`documents/full/documents_full.sqlite`
   documents：build_documents_index --mode full（默认 resume；必要时 --no-resume）
3. 校验 count：chunks≈6.1M+Δ；documents≈slim 篇数（基线 **4,557,627**）；chroma count 对齐
4. 切换挂载路径 / 重启服务（MED_RAG_RETRIEVAL_MODE=full）
```

> **断点续建 ≠ 增量补丁**：前者恢复同一次全量（按源文件 `processed_lines`）；后者消费增量源文件 upsert。详见 [`Dataset/documents/README.md`](../Dataset/documents/README.md)「逻辑分片」。

---

## 3. schema 升级（documents）

| 变更 | 做法 |
|------|------|
| 加列（如 `mesh_terms`） | `ALTER TABLE` + 回填脚本；`schema_version++` |
| 改主键/不兼容 | 新建库文件 → 切换路径 → 保留旧库至验证通过 |
| 06 回查改读 sqlite | 适配层：`SlimMetadataLookup` → `DocumentsIndexLookup`（同一字段 `pub_year`/`journal`） |

字段基线见 [`Dataset/documents/README.md`](../Dataset/documents/README.md)。

---

## 4. 建议交付物（本优化立项时再实现）

- [ ] 复用 12 `build_documents_index` 的 upsert + `progress.json`（全量 / 补丁同源）
- [ ] `scripts/patch_documents_index.py`（读增量 slim；批 upsert + `patch_manifest.json`）
- [ ] `scripts/rebuild_documents_index.py`（或等价：`build … --no-resume`）
- [ ] （可选）Chroma/BM25 增量 runbook
- [ ] 校验：`row_count`、抽样 pmcid、与 `/documents/{id}` / 重排回查联调
- [ ] 运维短文：备份 → 补丁 → 回滚；全量中断如何 `--status` 续跑

---

## 5. 进度记录

| 日期 | 事项 |
|------|------|
| 2026-07-27 | 创建规划；与 12 决定建全库文档索引、打包清单对齐 |
| 2026-07-27 | 文档索引采用「逻辑分片」：批提交 + progress 断点；补丁与全量共用 upsert |
| 2026-07-27 | 基线 full 索引已落盘：4,557,627 篇 · ~11.5 GB；后续增补优先 upsert 补丁，勿与 BM25 物理分片混淆 |
