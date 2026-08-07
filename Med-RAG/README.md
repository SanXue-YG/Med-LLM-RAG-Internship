# Med-RAG — 可独立运行的医学 RAG Demo 包

自包含整合仓库阶段 01–12 的问答能力 + React 演示前端。运行时只使用本目录内代码与 `data/`。

## 模式一句话（产品角色）

| 模式 | 角色 | Demo 能力 |
|------|------|-----------|
| **sample**（默认） | 更接近实际用户本机使用：可空启动、可上传增量 | 回形针上传 → **始终写入 sample 索引** |
| **full** | 预建大数据集迁入后只读问答 | **不能**用当前 Demo 上传更新全库；改 `.env` + 放资产即可问答 |

注意：即使 `.env` 已是 `full`，回形针新 XML **仍只进 sample**，不会更新正在查询的全库。交互更新请保持 sample（或上传后切回 sample 验证）。细节见 [`docs/数据存储与导入参考.md`](docs/数据存储与导入参考.md)。

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
| `backend/ingest` | 02–04 精简入库（一期固定写 sample） |
| `frontend` | React + Vite Demo |
| `data/` | 运行时索引与聊天记录（大文件默认 gitignore） |
| `docs/` | 代码说明、部署、数据导入参考、流程图 |

## 文档索引

| 文档 | 职责 |
|------|------|
| [`docs/部署文档.md`](docs/部署文档.md) | 环境、启动、切 full 的操作步骤 |
| [`docs/代码说明文档.md`](docs/代码说明文档.md) | 目录与模块入口、API 对应关系 |
| [`docs/数据存储与导入参考.md`](docs/数据存储与导入参考.md) | sample/full 数据路径、上传落盘、Dataset/Drive 迁移 |
| [`docs/流程图.md`](docs/流程图.md) | 问答与上传数据流简图 |
| [`data/README.md`](data/README.md) | `data/` 目录约定 |

## 空库 / 语料更新

若 sample 的 chroma / chunks 缺失，服务仍可启动；回形针上传写入 **sample** 三件套（`raw_uploads` → chunks / chroma_db / documents_sample）。全量资产请从本地 `Dataset/` 或约定的 [Google Drive 共享 Dataset](https://drive.google.com/drive/folders/1uK-2nbpOAWH61pWWrArpR8fdUzUihZ7H?usp=sharing) 迁入后再切 `MED_RAG_RETRIEVAL_MODE=full`（步骤见 [`docs/数据存储与导入参考.md`](docs/数据存储与导入参考.md) §6）。
