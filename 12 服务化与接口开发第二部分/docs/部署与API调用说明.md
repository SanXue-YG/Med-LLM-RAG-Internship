# 部署与 API 调用说明（阶段 0 骨架）

> 完整说明在阶段 4 补齐。

## 环境

- Conda：**`med-rag-verify`**（01–12 共用）
- 依赖：[`requirements.txt`](../requirements.txt)（相对 11 主要新增 `python-dotenv`）

```powershell
conda activate med-rag-verify
pip install -r requirements.txt   # 在「12 服务化与接口开发第二部分」目录下
```

## 启动 API

```powershell
cd "12 服务化与接口开发第二部分"
python scripts/run_api.py --no-reload
```

- 根：`GET /` → `stage=12-0`
- 健康：`GET /health`（来自阶段 11）
- 问答：`POST /api/v1/qa`（来自阶段 11；与后续 sessions **共用** SessionStore）

## 文档索引

- 样本：`Dataset/documents/sample/documents_sample.sqlite`（✅ 1000）
- 全量：`Dataset/documents/full/documents_full.sqlite`（✅ **4,557,627** · ~11.5 GB · 2026-07-27）

```powershell
python scripts/build_documents_index.py --mode sample   # 一般不必重跑
python scripts/build_documents_index.py --mode full --batch-size 50000
python scripts/build_documents_index.py --mode full --status
```
