# Med-RAG — 可独立运行的医学 RAG Demo 包

自包含整合仓库阶段 01–12 的问答能力 + React 演示前端。运行时只使用本目录内代码与 `data/`。

## 快速启动

```powershell
# 1) Python 环境（推荐沿用 med-rag-verify）
conda activate med-rag-verify
pip install -r requirements.txt

# 2) 配置
copy .env.example .env

# 3) 后端
python backend/scripts/run_api.py --no-reload
# → http://127.0.0.1:8000/docs

# 4) 前端（另开终端）
cd frontend
npm install
npm run dev
# → http://127.0.0.1:5173
```

## 目录

| 路径 | 说明 |
|------|------|
| `backend/app` | FastAPI（问答 / 会话 / 统计 / 文档 / 语料上传） |
| `backend/rag` | 05–10 管线 vendored |
| `backend/ingest` | 02–04 精简入库 |
| `frontend` | React + Vite Demo |
| `data/` | 运行时索引与聊天记录（大文件默认 gitignore） |
| `docs/` | 代码说明与部署文档 |

详情见 [`docs/部署文档.md`](docs/部署文档.md) · [`docs/代码说明文档.md`](docs/代码说明文档.md)。

## 空库 / 语料更新

若 `data/chroma` 与 `data/processed/chunks_sample.jsonl` 缺失，服务仍可启动；前端回形针按钮可上传 XML/JSONL 写入样本索引。也可用本机已有样本资产手动放入 `data/`（见部署文档）。
