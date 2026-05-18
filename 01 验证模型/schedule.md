# 第一阶段任务计划：验证本地模型 + 引入数据源

> 任务来源：`任务.txt`
> 阶段目标：完成「准备工作」——验证本地 LLM 可运行 + 接入 PubMed/PMC 数据源
> 注意：本阶段**不开发完整 RAG 系统**，只完成可行性验证与环境/数据准备
> 当前状态：**✅ 第一阶段全部交付完成**（2026-05-11 ~ 2026-05-13，Day 1 ~ Day 3）

---

## 📊 第一阶段汇报摘要（请优先阅读本节）

### 任务原文（节选）

> 验证本地语言模型运行情况并引入数据源（注意本次是准备工作，无需开始开发 rag 系统）

### 完成情况一览

| 子任务 | 状态 | 关键证据 |
|---|---|---|
| 模型选择与本地部署 | ✅ | Ollama 0.23.2 + `deepseek-r1:7b` Q4_K_M（4.68 GB，29/29 Metal offload） |
| 本地推理验证 | ✅ | 4 题中英文医学问答全部 `done_reason=stop` 自然完成，落盘 `outputs/model_test_results.json` |
| 开发环境就绪 | ✅ | `med-rag-verify` conda env + `requirements.txt` 134 行 + MPS True |
| PMC `oa_comm` 数据源接入 | ✅ | 100 篇结构化样本 `data/processed/sample.jsonl`（4.5 MB） |
| 字段抽取与质量验证 | ✅ | `parse_pmc_xml()` + pandas 字段非空率 97~100% |
| Chroma 向量库 smoke test | ✅ | 内存 + 持久化双跑通（`med-LLM-RAG.ipynb` §6） |

### 核心交付物（同梱本次提交）

| 类别 | 文件 / 目录 | 用途 |
|---|---|---|
| 任务管理 | `任务.txt` / `schedule.md`（本文件） | 任务原文 + 阶段计划与执行记录 |
| 主入口 | `med-LLM-RAG.ipynb` | 所有验证与解析操作的统一入口，每个 cell 可独立重跑 |
| 环境锁定 | `requirements.txt` | 134 行依赖版本 |
| 启动脚本 | `start_ollama.sh` / `start_jupyter.sh` | 一键拉起 Ollama 与 Jupyter，所有缓存/模型落到工程内 |
| 模型文件 | `ollama_models/`（4.4 GB） | deepseek-r1:7b Q4_K_M，工程内自包含 |
| 测试结果 | `outputs/model_test_results.json` | 4 题完整答案 + thinking + 性能指标 |
| 数据样本 | `data/processed/sample.jsonl`（100 篇） | PMC `oa_comm` 抽样，下一阶段 RAG 输入 |
| 学习笔记 | `笔记/01笔记.ipynb` + `笔记/01笔记附chroma.ipynb` | 量化机制、Ollama 存储原理、Chroma 工作机制 |

### 关键发现（直接关系到下一阶段）

1. **DeepSeek-R1 的 `thinking` 字段必须显式关掉**：Ollama 把推理链放在独立字段 `thinking`，默认开启时单题动辄 1500+ tok 思考链，HTTP 调用 180s 必超时。修正方法：API payload 设 `think=False`。下一阶段 RAG prompt 仍需保留此配置。

2. **本地 LLM 单答的医学准确性有缺陷，RAG 价值得到实证**：Q4「二甲双胍机制」模型答出 *"increases insulin secretion"*——这其实是磺脲类药物的机制，不是二甲双胍（后者主要是抑制肝糖原异生 + 改善胰岛素敏感性）。这条偏差天然就是「为什么要做 RAG」的最强论据，下一阶段引入文献后该题应被纠正。

3. **JATS XML 正文体量大**：抽样 100 篇中正文均长 39k 字符（最长 128k）。后续 chunking 时 `chunk_size` 需结合实际分布调（初步建议 800/100）。

4. **HTTP 流式推理速度 ~1.7 tok/s，比 CLI ~18.8 tok/s 慢 10×**：原因待查（散热降频 / HTTP 拆包开销 / CLI 内部路径不同），不影响功能验证但影响后续 RAG demo 体验。

5. **PMC 数据源工程方案**：原计划走「阿里云海外节点 + OSS」，Day 3 评估后发现仅 100 篇抽样无需开通服务器，改走 Mac 本地全流程（5.9 MB 增量包够用），节省 ¥30~50 云费用。下方阶段 3 保留原阿里云方案，未来若需 GB 级 baseline 包再启用。

### 下一步建议（待导师确认）

任务原文明确「本次是准备工作，**无需**开始开发 RAG 系统」。本次汇报严格按此边界完成。后续路径：

- **路径 A（保守）**：先按本阶段交付收口，由导师确认下一阶段范围与时间表。
- **路径 B（推荐）**：在本阶段成果之上加一个**最小 RAG 自验证**（详见文末「附加章节」），用 Chroma + LangChain 把"本地模型"和"数据源"接通一次，作为下一阶段的起点。预计 1 天工作量。

---

## 阶段总览

| 阶段 | 主题 | 预计耗时 | 状态 | 关键产出 |
| --- | --- | --- | --- | --- |
| 0 | 概念学习与硬件评估 | 0.5 ~ 1 天 | ✅ | M3 + 16 GB + 44 GB 磁盘，混合架构方案敲定 |
| 1 | 开发环境搭建 | 0.5 天 | ✅ | `med-rag-verify` env + `requirements.txt` 134 行 |
| 2 | 本地 LLM 部署与验证 | 1 天 | ✅ | Ollama + deepseek-r1:7b Q4_K_M，4 题验证通过 |
| 3 | PubMed/PMC 数据源接入 | 1 ~ 2 天 | ✅（Mac 本地全流程） | 100 篇 `sample.jsonl` 4.5 MB |
| 4 | 向量数据库选型确认 | 0.5 天 | ✅ | Chroma 内存 + 持久化双 smoke test 通过 |
| 5 | 阶段交付整理 | 0.5 天 | ✅（即本次汇报） | schedule.md + notebook + 笔记 整套 |

---

## 阶段 0：概念学习与混合架构方案

### 0.1 需要先理解的概念

- **LLM (Large Language Model)**：大语言模型，本任务中指 deepseek-r1 / Qwen3 等开源模型
- **RAG (Retrieval-Augmented Generation)**：检索增强生成，让模型在回答前先从知识库检索相关文本

  - RAG（Retrieval-Augmented Generation，检索增强生成）是一种AI技术，它通过在生成式大语言模型（LLM）回答问题前，先从外部知识库检索相关信息，从而改善内容质量，减少误报（幻觉）并提供最新数据。简单来说，就是让LLM在答题前先“翻书”（查阅文档或数据库），实现“精准检索 + 智能生成”。
- **量化 (Quantization)**：把模型权重压缩成低精度（如 Q4_K_M、Q5_K_M），降低显存/内存占用
  - `Q4_K_M`：4-bit 量化，体积小、速度快、精度损失稍多 → **本任务选用**
  - `Q5_K_M`：5-bit 量化，精度更好、占用更高
- **Embedding**：把文本转成向量（一串数字），用于相似度检索
- **Vector Database**：存储 embedding 并支持相似度搜索的数据库，本任务用 Chroma
- **Ollama**：本地一键运行 LLM 的工具，封装了模型下载与推理，对 Apple Silicon 的 Metal GPU 加速支持很好
- **Hugging Face**：模型/数据集托管平台，也可以直接 `pip` 用其 `transformers` 推理
- **LangChain**：把 LLM、Embedding、向量库、检索串起来的框架（本阶段先了解概念）
- **PubMed / PMC**：医学文献库，PMC OA 是开放获取版本
  - `oa_comm`：可商用的开放获取子集，是本任务唯一指定数据源
- **阿里云 ECS / 轻量应用服务器**：按量付费的云服务器，海外节点访问 NCBI 更稳定
- **阿里云 OSS**：对象存储，用于存放 PMC 大文件原始数据

### 0.2 选定方案：Mac 本地 + 阿里云混合架构（最低硬件配置）

#### 平台分工

| 职责 | 平台 | 说明 |
| --- | --- | --- |
| 开发环境（Conda、Python、代码） | Mac | 本地迭代最快 |
| LLM 推理验证 | Mac（Ollama） | Apple Silicon 跑 7B Q4_K_M 完全够用 |
| PMC oa_comm 下载与解压 | 阿里云轻量应用服务器（海外节点） | NCBI 国内直连慢，海外节点稳定 |
| 原始 tar.gz 存储 | 阿里云 OSS | oa_comm 全量上百 GB，避免占满 Mac 磁盘 |
| 抽样解析后的 jsonl | 同步回 Mac | 小样本本地处理足够 |
| 向量化 / 大规模 RAG | 阿里云 GPU（下阶段再开通） | 本阶段不需要 |

#### 模型与硬件下限

- **模型**：`deepseek-r1:7b` + `Q4_K_M` 量化 → 体积约 4.7GB，推理峰值内存约 5-6GB
- **Mac 最低**：Apple Silicon (M1 及以上) + 8GB 统一内存 + 10GB 可用磁盘
- **阿里云最低**：
  - 轻量应用服务器（新加坡/香港节点）2核2G，按月或按量付费
  - OSS 标准存储，按实际用量付费
  - 预计本阶段总花费 ¥30 ~ ¥50

### 0.3 硬件与账号准备清单

#### 本地 Mac ✅ 已确认

**硬件信息**

| 项 | 实际值 | 是否达标 |
| --- | --- | --- |
| 型号 | MacBook Air (Mac15,12) | ✅ |
| 芯片 | Apple M3（8 核，4 性能 + 4 能效） | ✅ Apple Silicon，支持 Metal |
| 内存 | 16 GB 统一内存 | ✅ 超过最低门槛 8GB |
| 可用磁盘 | 44.04 GB | ✅ 超过最低门槛 20GB |

**软件依赖**

- [x] Homebrew 已安装：`5.1.7`
- [x] Conda 已安装：`25.11.1`（路径 `/opt/miniconda3`）
- [x] PyPI 阿里云镜像访问正常（依赖下载已验证）
- [ ] GitHub / Hugging Face 访问（待阶段 2 拉取 Ollama 模型时实际验证）

**评估结论**：硬件完全满足本阶段需求，可直接跑 `deepseek-r1:7b Q4_K_M`，无需依赖云端推理。

#### 阿里云（待办，阶段 3 前完成）

- [ ] 已注册阿里云账号并完成实名认证
- [ ] 开通「轻量应用服务器」（暂不创建实例，等阶段 3 再开）
- [ ] 开通 OSS（创建一个 Bucket，例如 `med-rag-pmc`，地域选与服务器一致）
- [ ] 准备好 AccessKey 用于命令行/SDK 上传

### 0.4 决策记录

| 项 | 选定方案 | 备注 |
| --- | --- | --- |
| 模型 | `deepseek-r1:7b` `Q4_K_M` | 任务文档最低硬件档位 |
| 推理端 | Mac 本地 Ollama | M3 + 16GB + MPS 已满足 |
| 数据端 | 阿里云海外节点 + OSS | NCBI 国内直连慢 |
| 向量库 | Chroma（本阶段仅做 smoke test） | LEANN 作备选了解 |

**备选升级路径**（本阶段不启用，但 16GB 内存已满足条件）：
- 若想对比效果，后续可加跑 `qwen3:8b Q4_K_M`
- 若需要批量 embedding 或全量入库 PMC，再按量开通阿里云 GPU 实例

### 0.5 工程内存储策略（备份与清理）

**目标**：项目结束后整体备份方便、Mac 残留最少、新机一键恢复。

#### 资产分布全景

| # | 资产 | 位置 | 大小 | 来源 / 恢复方式 |
|---|---|---|---|---|
| 1 | Ollama 模型 | `ollama_models/` | 4.4 GB | `OLLAMA_MODELS` 环境变量重定向，`start_ollama.sh` 自动设置 |
| 2 | HuggingFace 缓存（未来） | `caches/huggingface/` | ?? | `HF_HOME` 环境变量重定向，`start_jupyter.sh` 自动设置 |
| 3 | PyTorch 缓存（未来） | `caches/torch/` | ?? | `TORCH_HOME` 环境变量 |
| 4 | Transformers 缓存（未来） | `caches/transformers/` | ?? | `TRANSFORMERS_CACHE` 环境变量 |
| 5 | PMC 原始数据 | `data/raw/` | 抽样后 < 1 GB | 阿里云海外节点下载，本地仅留样本 |
| 6 | PMC 解析样本 | `data/processed/sample.jsonl` | < 100 MB | 工程内 |
| 7 | Chroma 持久化 | `chroma_db/` | < 1 GB | 工程内 |
| 8 | 模型测试结果 | `outputs/model_test_results.json` | < 1 MB | 工程内 |

**结论**：所有大型可下载数据都"截"在工程内，只要复制 `01 验证模型/` 整个文件夹即可完整备份。

#### Mac 上不可避免的系统级残留

| 项 | 位置 | 大小 | 处理方式 |
|---|---|---|---|
| Conda 虚拟环境 | `/opt/miniconda3/envs/med-rag-verify/` | 1.4 GB | `requirements.txt` 即可重建，不需备份 |
| Jupyter kernelspec | `~/Library/Jupyter/kernels/med-rag-verify/` | 24 KB | 一行命令重建 |
| Ollama 二进制 | `/opt/homebrew/Cellar/ollama/` | < 50 MB | `brew install ollama` 重装 |
| Ollama 身份密钥 | `~/.ollama/id_ed25519*` | < 1 KB | 默认副产物，无需备份 |

#### 项目完结后的"清理 Mac"配方

按需执行（不可逆，确认后再操作）：

```bash
# 1) 停止 Ollama 后台服务（若开了）
brew services stop ollama 2>/dev/null

# 2) 删除虚拟环境（1.4 GB）
conda env remove -n med-rag-verify -y

# 3) 删除 Jupyter kernelspec
jupyter kernelspec remove med-rag-verify -y

# 4) 删除 ~/.ollama 残留（可选，保留也无害）
rm -rf ~/.ollama

# 5) 卸载 Ollama 二进制（可选，若 Mac 完全不需要 Ollama）
brew uninstall ollama

# 此时 Mac 上 0 残留，项目完整保存在 01 验证模型/ 一个文件夹里
```

#### 新机恢复配方

```bash
# 1) 装 Homebrew、Conda（略，参考各自官网）

# 2) 把备份回来的工程文件夹放到目标位置
#    例如：~/Desktop/work/实习/谷歌/01 验证模型/

# 3) 重建虚拟环境
conda create -n med-rag-verify python=3.11 -y
conda activate med-rag-verify
pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 4) 注册 Jupyter kernel
python -m ipykernel install --user --name med-rag-verify \
    --display-name "Python (med-rag-verify)"

# 5) 装 Ollama 二进制（模型已在工程内 ollama_models/，无需重新下载）
brew install ollama

# 6) 启动服务：模型自动从工程内加载
cd "01 验证模型"
./start_ollama.sh
./start_jupyter.sh   # 另一个终端窗口
```

---

## 阶段 1：开发环境搭建 ✅ 已完成

### 1.1 安装 Conda

- [x] 已存在 Miniconda：版本 `25.11.1`，路径 `/opt/miniconda3`

### 1.2 创建虚拟环境

执行命令：

```bash
conda create -n med-rag-verify python=3.11 -y
```

- [x] 环境已创建：`med-rag-verify`
- [x] Python 版本：3.11.15
- [x] 环境路径：`/opt/miniconda3/envs/med-rag-verify`

### 1.3 安装依赖（使用阿里云镜像加速）

执行命令：

```bash
pip install -i https://mirrors.aliyun.com/pypi/simple/ \
    torch langchain chromadb pandas datasets huggingface_hub requests tqdm lxml
```

> 说明：本阶段 `torch` 用于后续 embedding；`lxml` 用于解析 PMC XML 文献

- [x] 9 个核心包 + 全部传递依赖已安装（共 108 条记录）
- [x] 使用阿里云镜像下载，无超时/失败

### 1.4 验证结果

- [x] 全部 9 个库 import 成功（无报错）
- [x] `requirements.txt` 已导出到任务目录（108 行）

| 库 | 安装版本 |
| --- | --- |
| torch | 2.11.0 |
| langchain | 1.2.18 |
| chromadb | 1.5.9 |
| pandas | 3.0.2 |
| datasets | 4.8.5 |
| huggingface_hub | 1.14.0 |
| requests | 2.33.1 |
| tqdm | 4.67.3 |
| lxml | 6.1.0 |

### 1.5 PyTorch 设备能力

- [x] `MPS available : True` —— Apple Silicon GPU 加速可用
- [x] `MPS built     : True`
- [x] `CUDA available: False`（Mac 无 NVIDIA GPU，符合预期）

**结论**：后续 embedding 推理可走 MPS 加速，性能比纯 CPU 快数倍。

### 1.6 使用提示

#### 终端激活环境

每次开新终端、做本任务相关操作前，先激活环境：

```bash
conda activate med-rag-verify
```

激活后终端提示符会从 `(base)` 变成 `(med-rag-verify)`。

#### Cursor 打开 Notebook 的固定流程（已踩坑）

Cursor 的 Python 扩展无法自动发现 conda 环境，因此采用「外部 Jupyter Server」模式：

1. **额外装的依赖**（已完成）：
   ```bash
   pip install ipykernel jupyter
   python -m ipykernel install --user --name med-rag-verify \
       --display-name "Python (med-rag-verify)"
   ```
2. **每次工作前**，在 Mac 终端启动 Jupyter Server（**保持窗口不关**）：
   ```bash
   conda activate med-rag-verify
   jupyter notebook --no-browser --port=8888
   ```
   终端会打印 `http://localhost:8888/tree?token=...`，复制完整 URL。
3. **首次连接 Cursor**：打开 `med-LLM-RAG.ipynb` → 右上角 kernel → 「选择其他内核...」→ **Existing Jupyter Server** → 粘贴 URL → 选 `Python (med-rag-verify)`。
4. 后续 Cursor 会记住该 server，下次打开自动重连；若断了重走第 3 步即可。

---

## 阶段 2：本地 LLM 部署与验证 ✅ 已完成

### 2.1 安装 Ollama

```bash
brew install ollama
```

- [x] Ollama 版本：`0.23.2`
- [x] 服务监听：`http://127.0.0.1:11434`
- [x] 顺带装上 `mlx`、`mlx-c`（Apple Silicon ML 加速库）
- [x] **按需启动模式**（不挂后台服务）：在工程根目录跑 `./start_ollama.sh`，模型存储指向工程内目录

> 说明：之前用 `brew services start ollama` 后台常驻；考虑到 Mac 还要做其他工作，已改为「用时启动 + 工程内模型管理」。详见 2.2 与 2.6。

### 2.2 拉取模型

```bash
ollama pull deepseek-r1:7b
```

- [x] 模型已下载
- [x] 实际体积：4.68 GB
- [x] 量化等级：**Q4_K_M**（符合任务文档要求）
- [x] 参数量：7.6B
- [x] 底层架构：qwen2
- [x] 下载耗时约 100 秒，平均 50+ MB/s
- [x] **存储位置已迁移到工程内**：`01 验证模型/ollama_models/`（默认是 `~/.ollama/models/`）

### 2.2.1 工程内模型管理（按需启动模式）

为方便管理与工程随项目移动，模型与服务启动方式做了改造：

| 项 | 值 |
|---|---|
| 模型目录 | `01 验证模型/ollama_models/`（含 `blobs/` 与 `manifests/`） |
| 启动脚本 | `01 验证模型/start_ollama.sh` |
| 关键机制 | 脚本内 `export OLLAMA_MODELS="${SCRIPT_DIR}/ollama_models"` |
| 启动方式 | 在终端执行 `./start_ollama.sh`，保持窗口开着，Ctrl+C 停止 |
| 后台服务状态 | 已 `brew services stop ollama`，**不再开机自启** |

**每次工作流程：**
1. 在终端 `cd "01 验证模型"`，运行 `./start_ollama.sh`
2. 看到日志 `Listening on 127.0.0.1:11434 (version 0.23.2)` 即启动成功
3. 不再使用本服务时，回到该终端按 Ctrl+C

---

### 📌 Day 1 进度小结（2026-05-11）

> 本节是 Day 1 工作的快照。后面的章节是计划要做或部分已做的内容。

#### 已完成阶段

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 0 | 概念学习 + 硬件评估 + 混合架构方案 + 决策记录 | ✅ |
| 1 | 开发环境搭建（Conda + Python + 9 依赖 + 验证）| ✅ |
| 2.1 | 安装 Ollama 0.23.2 | ✅ |
| 2.2 | 拉取 `deepseek-r1:7b` Q4_K_M（4.4 GB） | ✅ |
| 2.2.1 | 工程内模型管理（迁移 + 启动脚本） | ✅ |

#### 关键里程碑

1. **硬件评估完成**：MacBook Air M3 / 16 GB / 44 GB 可用磁盘 → 满足本任务最低要求
2. **Conda 环境 `med-rag-verify` 建好**：Python 3.11.15 + torch 2.11.0（MPS True）+ 8 个项目库
3. **Jupyter / Cursor 集成跑通**：用 `Existing Jupyter Server` 模式连接，绕过 Cursor 默认 Python 扩展无法发现 conda 环境的问题
4. **Ollama 安装 + 模型下载完毕**：`deepseek-r1:7b` Q4_K_M，单次冷启动推理 ~18.8 tok/s 验证通过
5. **工程容器化**：4.4 GB 模型 + 未来的 HF/Torch 缓存全部装在工程目录内，Mac 残留最小化
6. **启动脚本就位**：`start_ollama.sh` + `start_jupyter.sh`，通过环境变量重定向所有大数据位置
7. **bug 修复**：`PROJECT_DIR` 解析采用三道防线（环境变量 → 向上搜 `任务.txt` → 报错）

#### Day 1 关键产出（工程目录文件清单）

```
01 验证模型/
├── 任务.txt
├── schedule.md              # 持续更新中
├── requirements.txt         # 108 → 134 行（加了 ipykernel + jupyter）
├── med-LLM-RAG.ipynb        # 27 个 cell，章节 1-2 已跑通
├── start_ollama.sh          # ⭐ 新
├── start_jupyter.sh         # ⭐ 新
├── ollama_models/  (4.4 GB) # ⭐ 新（Ollama 模型已迁入）
├── caches/         (空)     # ⭐ 新（HF/Torch/Transformers 缓存占位）
├── data/
│   ├── raw/                 # 阶段 5 才会填
│   └── processed/
└── outputs/
```

#### 学习的知识点

- ✅ **C. Ollama 存储原理**：CAS（content-addressable storage）/ manifests + blobs / Docker 同款方案

#### 待完成（Day 2 起点）

- [ ] **2.4** 跑 notebook cell 9 → 4 个中英文医学问题完整测试 + 落盘 `outputs/model_test_results.json`
- [ ] **2.5** 在性能小结表里填入实测内存占用数字
- [ ] **学习剩余知识点**（B 环境变量/D Jupyter 架构/E Conda/F CWD/G Bash，任选）
- [ ] **进入阶段 3**：PMC `oa_comm` 数据源接入（阿里云海外节点 + OSS）

#### 当前 Mac 上的占用情况

| 位置 | 大小 | 备份策略 |
| --- | --- | --- |
| `01 验证模型/`（工程） | ~4.4 GB | **整体备份**这一个 |
| `/opt/miniconda3/envs/med-rag-verify/` | 1.4 GB | 用 `requirements.txt` 一键重建 |
| `~/Library/Jupyter/kernels/med-rag-verify/` | 24 KB | 一行命令重建 |
| `/opt/homebrew/Cellar/ollama/` | < 50 MB | `brew install` 重装 |
| `~/.ollama/` | 16 KB | Ollama 默认副产物，可忽略 |

---

### 2.3 首次推理 smoke test

通过 `/api/generate` 端点测试单个医学问题：

```
Q: In one sentence, what is diabetes?
A: Diabetes is a condition characterized by the body's inability to effectively regulate
   blood sugar levels, typically resulting from impaired insulin function or sensitivity...
```

- [x] 回答医学准确（覆盖 insulin / blood glucose / hyperglycemia / hypoglycemia）
- [x] 推理速度：**18.8 tok/s**（M3 + Q4_K_M 典型水平）
- [x] 388 tokens 输出，含冷启动总耗时 39.6s

### 2.4 完整多问题验证 ✅ 已完成（详见 Day 2 进度小结）

测试问题集（`med-LLM-RAG.ipynb` cell 12 修正版）：

1. `What are the common symptoms of type 2 diabetes?`
2. `请简要解释高血压的主要风险因素。`
3. `Summarize the relationship between chronic inflammation and cardiovascular disease.`
4. `What is the mechanism of action of metformin?`

4 题全部 `done_reason=stop` 自然结束、0 截断，结果保存到 `outputs/model_test_results.json`。**关键改造**：必须设 `payload["think"] = False`，否则 deepseek-r1 默认会输出大段独立 `thinking` 字段，而 `response` 长时间为空，旧 cell 看似"答案空白"。

### 2.5 性能指标小结（Day 2 实测）

| 维度 | 数值 | 备注 |
|---|---|---|
| 模型 | `deepseek-r1:7b` Q4_K_M | 4.68 GB，29/29 层 Metal offload |
| Day 1 单题 smoke（CLI `ollama run`） | **~18.8 tok/s** | 388 tok 输出，含冷启动 39.6s |
| Day 2 多题 HTTP 流式（think=False） | **~1.7 tok/s** | 平均 31.9s/题，4 题 0 截断 |
| 速度差异 | **10× 差距**，原因待 Day 3 追查 | 候选：被动散热降频 / HTTP 拆包开销 / CLI 内部 batching |
| 内存占用 | 进程驻留期间约 5-6 GB | 与 Day 1 估算一致 |
| 加速方式 | Metal (MPS) via Ollama 内置 | 日志确认 GPU `Apple M3 / 11.8 GiB`

**结论**：模型完全满足本任务需要，无需切换到 Qwen3 或云端方案。

---

### 📌 Day 2 进度小结（2026-05-12）

> 紧接 Day 1，本节完成「**本地 LLM 功能验证**」与若干学习笔记的产出。

#### 已完成阶段

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 2.4 | 4 题中英文医学问题完整验证（cell 12 修正版） | ✅ |
| 2.5 | 性能小结表，用实测数据替换 Day 1 预测值 | ✅ |
| —  | 修复 cell 10 的 ReadTimeout（关闭 deepseek-r1 thinking） | ✅ |
| —  | 学习笔记 `笔记/01笔记.ipynb` 新增「训练时显存优化 vs 推理时离线量化」 | ✅ |
| —  | 学习笔记 `笔记/02笔记.ipynb` 新建「Ollama 多模型存储原理」 | ✅ |
| —  | 下阶段规划 `02 LangChain_RAG/schedule.md` 骨架就绪 | ✅ |

#### 关键发现（三条都对后续阶段有影响）

1. **DeepSeek-R1 的 `thinking` 字段必须单独处理**
   - Ollama 对 `deepseek-r1:*` 系列返回的 JSON 把推理链放在独立字段 `thinking`，**`response` 字段在推理结束前一直为空**。
   - 默认 `think=true` 时单题动辄 1500+ tok 思考链，旧 cell 的 180s timeout 直接打不完，造成全数 `ReadTimeout`。
   - 修正：`payload["think"] = False` + `num_predict=300` + `timeout=300`，4 题全部 `done_reason=stop` 自然完成。
   - **影响后续**：阶段 5（RAG 链路）默认也要关 `thinking`，并在 prompt 中明确"不要展示推理步骤"。

2. **M3 + Q4_K_M 实测 decode 速度只有 ~1.7 tok/s，与 Day 1 命令行测得的 18.8 tok/s 相差 10×**
   - 速度本身偏慢；30 秒一道题在 RAG demo 里会变成明显痛点。
   - **原因待 Day 3 追查**，候选清单：
     - MacBook Air 被动散热长跑降频
     - HTTP 流式 + 逐行 JSON 拆包的额外开销
     - Day 1 用 CLI `ollama run`，内部 batching/采样路径可能不同
     - `n_ctx=4096` 默认值是否触发了某种慢路径
   - 备选缓解（若 Day 3 找不到提速空间）：换 `deepseek-r1:1.5b` 蒸馏版、更激进量化、或后续接入云端模型做对照。

3. **LLM 单答的医学准确性需要 RAG 加持（任务存在的本质动因）**
   - Q4「二甲双胍机制」模型答："*increasing insulin secretion from the pancreas, improving insulin sensitivity, and inhibiting gluconeogenesis*"
   - **第一项错误**：二甲双胍**不增加胰岛素分泌**（那是磺脲类药物的机制）；它主要是**抑制肝糖原异生 + 改善胰岛素敏感性**。
   - 这一条天然就是「为什么要做 RAG」的实证——下一阶段引入 PMC 文献后，应能在此类细节上提供更可靠的依据。

#### Day 2 关键产出

- `outputs/model_test_results.json`：4 题完整答案 + thinking 字段 + 性能指标
- `med-LLM-RAG.ipynb` cell 12：修正版功能验证 cell（保留原 cell 11 作为历史对比）
- `笔记/01笔记.ipynb` 新增章节：训练时显存优化 vs 推理时离线量化
- `笔记/02笔记.ipynb`（新建）：Ollama 多模型存储原理（CAS / blobs / manifests）
- `02 LangChain_RAG/schedule.md`（新建）：下阶段工程的骨架规划，明确「benchmark_batch.py 只复用调用方式 + Key」

#### 学习的知识点

- ✅ **A. 量化机制深入**：GGUF 离线量化 vs DeepSpeed/bitsandbytes 训练时显存优化，两条路线时机/框架/能否训练 全面对比
- ✅ **C. Ollama 多模型存储**：CAS（blobs 平铺 + manifests 树），与 Docker 镜像同构

#### 待完成（Day 3 起点）

- [ ] 排查 1.7 vs 18.8 tok/s 的速度差（散热？HTTP 开销？CLI 路径不同？）
- [ ] **进入阶段 3**：PMC `oa_comm` 数据源接入（阿里云海外节点 + OSS）
- [ ] Cursor 把 Python interpreter 切到 `med-rag-verify`（消掉 `requests` 等 lint 警告，今天延期事项）
- [ ] 视任务进展，决定是否启动 `02 LangChain_RAG` 工程容器化

---

### 📌 Day 3 进度小结（2026-05-13）

#### 路线调整：阿里云延后，改为 Mac 本地全流程

下方阶段 3 原方案以「阿里云海外节点 + OSS」为主导。讨论中发现两个问题：

1. **阿里云 30 GB 系统盘装不下 baseline 全量包**（单包 43M ~ 13G，全量上百 GB），目前只用 100 篇抽样根本不需要这个体量。
2. **本任务只交付「抽样验证」**，无需进入大规模数据工程，开通服务器属于过度准备。

→ 决定改走 **Mac 本地全流程**：抓 `oa_comm/xml/` 下最小的增量小包（5.9 MB 量级）即可满足 100 篇抽样。

#### Day 3 实际执行（见 `med-LLM-RAG.ipynb` §5，9 步留档）

| 步 | 任务 | 产物 | 状态 |
|---|---|---|---|
| 5.1 | 抓 `oa_comm/xml/` 目录，正则筛 `.tar.gz` + 大小排序 | 123 个候选清单 | ✅ |
| 5.2 | `requests` 流式下载 `oa_comm_xml.incr.2026-02-10.tar.gz` | `data/raw/*.tar.gz` (5.87 MB / 48s) | ✅ |
| 5.3 | `tarfile` 解压 | `data/raw/extracted/` (284 篇 XML / 27 MB) | ✅ |
| 5.4 | 打印第一篇 XML 前 80 行 | 控制台留档 JATS 结构 | ✅ |
| 5.5 | 定义 `parse_pmc_xml()`（lxml + XPath） | 函数对象 | ✅ |
| 5.6 | 单篇验证抽取 | 字段长度 OK，但 `title` 异常 2973 字（参考文献污染） | ⚠️ |
| 5.7 | 批量解析前 100 篇 | `data/processed/sample.jsonl` (4.5 MB, 100/100 全部成功) | ✅ |
| 5.8 | pandas 字段非空率 + 长度分布 | pmcid/title/body/journal/pub_year 100%，abstract 97%，body 均长 ~39k 字 | ✅ |

#### Day 3 关键产出

- `data/raw/oa_comm_xml.incr.2026-02-10.tar.gz`：原始 5.87 MB 压缩包
- `data/raw/extracted/`：284 篇 JATS XML
- `data/processed/sample.jsonl`：100 篇结构化样本，下一阶段 chunking / embedding 的输入

#### Day 3 关键发现

1. **NCBI 直连国内带宽偏低**（0.12 MB/s），5.9 MB 还能忍；如果未来要拉 GB 级的 baseline 包再考虑海外节点。
2. **`//article-title` XPath 没限定到 `<front>`**，会把参考文献区里被引文献的 title 也抽进来 → §5.6 单篇 title 异常 2973 字。正确写法：`//front//article-title[1]`。下次开工先修这个 bug 并重跑 §5.7-8。
3. **JATS XML 体量比想象的大**：解压后单篇平均 95 KB，正文均长 39k 字符，远大于常规 chunk_size。下阶段 chunking 参数要好好调。

#### 阶段任务交付状态

老师的第一阶段交付要求：**「验证本地语言模型运行情况 + 引入数据源」**

- ✅ 本地 LLM（deepseek-r1:7b Q4_K_M）已通 4 题验证（Day 2）
- ✅ PMC `oa_comm` 数据源已成功引入，100 篇结构化样本就绪（Day 3）
- → **第一阶段交付完成**，可与老师确认后续路径

#### 待完成（Day 4 起点）

- [ ] 修 `parse_pmc_xml()` 的 title XPath bug，重跑 §5.7-8
- [ ] 跟老师汇报第一阶段成果，确认下一步是否进入 RAG 开发
- [ ] **附加自验证任务**：见文末「附加：最小 RAG 自验证」章节
- [ ] 排查 1.7 vs 18.8 tok/s 的速度差（沿留）
- [ ] Cursor Python interpreter 切到 `med-rag-verify`（沿留）

---

## 阶段 3：PubMed / PMC 数据源接入 ✅ 已完成（Mac 本地全流程）

> ⚠️ **实际执行版本**：Day 3 改为「Mac 本地全流程」完成，见上方 `📌 Day 3 进度小结`。
> 下方 3.1-3.8 保留为**原阿里云方案备查**，未来若需要 GB 级 baseline 包时再启用，本次不执行。

### 3.1 了解数据源结构

数据源：`https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_bulk/`
本任务只用 `oa_comm/`，里面包含按时间分批的 `.tar.gz` 文件，解压后是大量 XML / 纯文本文献。
全量数据可能达上百 GB，因此**只抽样**。

### 3.2 开通并配置阿里云轻量服务器

- [ ] 开通「轻量应用服务器」，地域选**新加坡或香港**（直连 NCBI 更快）
- [ ] 规格选 2核2G（最便宜），系统选 Ubuntu 22.04
- [ ] SSH 登录后基础配置：
  ```bash
  sudo apt update && sudo apt install -y python3-pip python3-venv wget tar
  pip3 install --user requests lxml pandas tqdm oss2
  ```
- [ ] 安装阿里云 OSS CLI 工具 `ossutil`，配置 AccessKey

### 3.3 抽样下载（在阿里云上执行）

- [ ] 浏览 `oa_bulk/oa_comm/` 目录，挑选 1 个最小的批次 `.tar.gz`
- [ ] 用 `wget` 下载到云服务器 `~/data/raw/`
- [ ] 记录文件大小、下载耗时、解压后文件数量
- [ ] 上传原始 `.tar.gz` 到 OSS 备份：
  ```bash
  ossutil cp ~/data/raw/xxx.tar.gz oss://med-rag-pmc/raw/
  ```

### 3.4 解析单篇文献（云上）

- [ ] 解压一个文件，确认目录结构
- [ ] 用 `lxml` 解析其中一篇 XML，抽取：
  - PMCID
  - 标题
  - 摘要
  - 正文段落
  - 作者 / 发表时间（可选）

### 3.5 批量抽取到 jsonl（云上）

- [ ] 写一个最小脚本：遍历样本（先取 100 ~ 500 篇）
- [ ] 保存为 `data/processed/sample.jsonl`（每行一篇）
- [ ] 上传到 OSS：`oss://med-rag-pmc/processed/sample.jsonl`

### 3.6 同步样本回 Mac

- [ ] 在 Mac 上用 `ossutil` 或 `scp` 拉取 `sample.jsonl`
- [ ] 放到本地 `data/processed/sample.jsonl`
- [ ] 用 pandas `df.head()` 验证字段完整

### 3.7 验收

- [ ] 至少 100 篇样本能完整解析
- [ ] 字段无大面积空值
- [ ] 样本同时存在于 OSS 和 Mac 本地
- [ ] 输出样本可以被后续 chunking / embedding 使用

### 3.8 成本控制

- [ ] 抽样阶段结束后，**关停或释放**轻量服务器实例（避免持续计费）
- [ ] 原始数据保留在 OSS（按量付费很便宜）
- [ ] 记录本阶段实际花费

---

## 阶段 4：向量数据库选型确认 ✅ 已完成

> 本阶段只做「能用」验证，不做真实入库。实际验证在 `med-LLM-RAG.ipynb` §6 完成。

### 4.1 Chroma 最小可用性 ✅

实际跑通的代码（见 `med-LLM-RAG.ipynb` §6）：

- [x] **内存模式 smoke test**：`chromadb.Client()` + `get_or_create_collection` + `add` + `query`，命中 hypertension / diabetes 相关条目
- [x] **持久化模式 smoke test**：`PersistentClient(path="01 验证模型/chroma_db/")`，集合数 1，已成功落盘
- [x] **工作机制理解**：默认走 `DefaultEmbeddingFunction`（ONNX Runtime + 内置 all-MiniLM-L6-v2，79 MB），开箱即用、不依赖 `sentence_transformers`；想换 BGE / PubMedBERT 时再装 `sentence-transformers` 并显式传 `embedding_function`。详细原理与可运行示例见 `笔记/01笔记附chroma.ipynb`。

### 4.2 备选 LEANN

- [x] 已了解 LEANN 与 Chroma 差异（LEANN 偏检索算法侧，Chroma 自带存储 + 索引 + metadata，集成更完整）
- [x] **选定 Chroma** 的理由：任务文档首选 + 部署门槛低 + LangChain 原生支持，无需再切 LEANN

---

## 阶段 5：阶段交付整理 ✅ 已完成（即本次汇报）

### 5.1 实际交付清单（同梱本次提交）

| 文件 / 目录 | 内容 | 对应原计划的哪份 md |
|---|---|---|
| `schedule.md`（本文件） | 阶段计划 + 执行记录 + 顶部汇报摘要 | 整合 `hardware.md` / `data_pipeline.md` / `cost_report.md` / `next_steps.md` |
| `med-LLM-RAG.ipynb` | 所有验证操作的统一入口，每个 cell 可独立重跑 | 整合 `model_report.md` 的核心证据 |
| `requirements.txt` | 134 行依赖版本 | 同原计划 |
| `data/processed/sample.jsonl` | 100 篇 PMC `oa_comm` 结构化样本 | 同原计划 |
| `outputs/model_test_results.json` | 4 题完整答案 + thinking + 性能指标 | 作为 `model_report.md` 的原始证据 |
| `start_ollama.sh` / `start_jupyter.sh` | 一键启动 + 缓存/模型全部落到工程内 | 工程容器化方案的执行入口 |
| `ollama_models/`（4.4 GB） | deepseek-r1:7b Q4_K_M 模型本体 | 复现性保障 |
| `笔记/01笔记.ipynb` | 量化机制（GGUF vs DeepSpeed）、Ollama 存储原理 | 学习笔记 |
| `笔记/01笔记附chroma.ipynb` | Chroma 工作原理 + 可运行最小示例 | 学习笔记 |

> 原计划的 `hardware.md` / `cost_report.md` / `data_pipeline.md` / `next_steps.md` 都已合并到 `schedule.md`「汇报摘要」与各阶段执行记录中，**无需单独维护多份 md**，减少冗余。

### 5.2 自检 Checklist

- [x] 本地模型可稳定推理（4 题验证 + 多次 smoke test 无崩溃）
- [x] PMC 样本可解析、可读取（pandas 字段非空率 97~100%）
- [x] Chroma 已安装并通过 smoke test（内存 + 持久化两种模式）
- [x] 所有脚本可被复现（`start_ollama.sh` + `start_jupyter.sh` + notebook cell 顺序明确）
- [x] 工程内自包含：复制整个 `01 验证模型/` 目录即可在新机恢复

---

## 附加章节（提案）：最小 RAG 自验证 — 不在第一阶段交付范围内

> ⚠️ **本节内容不是第一阶段的交付项**，仅作为下一阶段路径的**提案与可行性预案**。
> 任务原文明确「本次是准备工作，**无需**开始开发 rag 系统」，本次汇报严格遵守此边界，不提前实施本节。

### 为何提出这个提案

1. 把"本地模型"和"数据源"接通一次，能拿到一个**端到端跑通的最小 demo**，比单独的两块成果更有说服力。
2. Day 2 发现 deepseek-r1:7b 在二甲双胍机制那题答错。RAG 之后这题是否被纠正，能直接证明数据源的价值。
3. 提前暴露 chunking / embedding / prompt 三个关键参数的工程问题，为正式 RAG 开发节省试错时间。

### 目标

跑通一条**最小 RAG 链路**：`用户问题 → embedding → Chroma 检索 top-k chunks → 拼 prompt → 本地 ollama LLM → 答案`，并用 Day 2 的 4 个医学问题做"无 RAG vs 有 RAG"对比。

### 技术栈（最小化）

| 角色 | 选择 | 理由 |
|---|---|---|
| Embedding 模型 | `sentence-transformers/all-MiniLM-L6-v2`（本地，22 MB） | 轻量、CPU 友好、跑通门槛最低；后续可换 PubMedBERT 对比 |
| 切块 | `RecursiveCharacterTextSplitter`，chunk_size=800 / overlap=100 | 配合 PMC 长正文，常规 RAG 起步参数 |
| 向量库 | **Chroma**（`PersistentClient`，落到工程内 `chroma_db/`） | 任务首选 + 已在 schedule §4.1 验证过 smoke test |
| LLM | 已有的 `deepseek-r1:7b` (Ollama, 本地)，关闭 `thinking` | 复用 Day 2 已验证的本地模型 |
| 编排框架 | `langchain` + `langchain-chroma` + `langchain-ollama` + `langchain-huggingface` | 任务指定 LangChain |

> 这一步用到的 4 个 LangChain 子包，**当前 `med-rag-verify` 环境只装了 `langchain` 主包**。下一步开工前要 `pip install` 这 4 个并更新 `requirements.txt`。

### 步骤（计划写入 `med-LLM-RAG.ipynb` §6）

**6.0 前置修复**
- [ ] 修 `parse_pmc_xml()` 的 `//article-title` → `//front//article-title[1]`
- [ ] 重跑 §5.7 / §5.8 验证 title 长度回到正常区间（< 500 字）

**6.1 准备 embedding 模型**
- [ ] `pip install sentence-transformers langchain-huggingface langchain-chroma langchain-ollama`
- [ ] 首次加载 MiniLM 会自动下到 `caches/huggingface/`（已通过 `start_jupyter.sh` 设置 `HF_HOME`）
- [ ] 验证：对 "diabetes" 做一次 encode，确认输出 384 维向量

**6.2 切块**
- [ ] 读 `sample.jsonl`，对每篇文章把 `abstract + body` 拼成一段文本
- [ ] 用 `RecursiveCharacterTextSplitter` 切，metadata 带 `{pmcid, title, journal, pub_year}`
- [ ] 打印切块统计：总 chunk 数、长度均值/分位数

**6.3 入库 Chroma**
- [ ] `PersistentClient(path=chroma_db/)`，集合名 `pmc_oa_comm_sample`
- [ ] 批量 `add` 所有 chunk（含 metadata）
- [ ] 验证：`count()` 应等于上一步切块数

**6.4 单次检索 smoke test**
- [ ] query="metformin mechanism of action", k=4
- [ ] 打印检索到的 top-4 chunk 文本片段 + metadata + 相似度分数
- [ ] 肉眼判断检索质量

**6.5 LangChain LCEL 接通**
- [ ] `retriever = Chroma.as_retriever(search_kwargs={"k": 4})`
- [ ] `prompt = ChatPromptTemplate.from_template("Answer the question based ONLY on the following context:\n{context}\n\nQuestion: {question}\nAnswer:")`
- [ ] `llm = ChatOllama(model="deepseek-r1:7b", think=False, num_predict=300)`
- [ ] `chain = {"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | llm | StrOutputParser()`

**6.6 对比 Day 2 的 4 个医学问题**
- [ ] 跑「无 RAG 直答」(Day 2 已有，从 `model_test_results.json` 读) vs 「有 RAG 答」(新跑)
- [ ] 重点关注 Q4 二甲双胍机制：RAG 答中是否还出现"increases insulin secretion"（错误）？

**6.7 留档**
- [ ] 输出 `outputs/min_rag_compare.json`：4 题 × {无 RAG 答, 有 RAG 答, 检索到的 chunk 列表, 耗时}
- [ ] 在笔记本里写一段"为什么 RAG 在医学场景下必要"的总结

### 验收

- [ ] 端到端链路 4/4 题能跑出非空答案
- [ ] 至少 1 题（特别是二甲双胍机制）能看到 RAG 后比 Day 2 直答**更接近真实文献**
- [ ] `chroma_db/` 已持久化，重启 notebook 后还能用

### 这一步的非目标（避免范围蔓延）

- ❌ 不做多 embedding 模型对比（MiniLM vs PubMedBERT 留给 `02 LangChain_RAG`）
- ❌ 不做多 LLM 对比（deepseek vs qwen vs 智增增 API 留给 `02 LangChain_RAG`）
- ❌ 不做 chunking 参数网格搜索
- ❌ 不做 RAGAS / TruLens 量化评估，只做肉眼对比

### 决策点（请导师裁定）

1. **要不要做**：作为下一阶段的第一步纳入开发？还是先按 `02 LangChain_RAG/` 中的完整 RAG 工程展开？
2. **在哪儿做**：用 `01 验证模型/med-LLM-RAG.ipynb` 加 §6 章节（推荐，方便和上游链路对比），还是另起 `02 最小RAG/` 等新工程目录（注：若新增工程，现 `02 LangChain_RAG/` 序号可能顺延）？
3. **范围控制**：是否同意上方「非目标」一节，先做最小可对比 demo、不做 embedding / LLM / chunking 的多维度网格对比？

---

## 学习资源（按需查阅）

- Ollama 官方文档：https://github.com/ollama/ollama
- LangChain RAG 教程：https://python.langchain.com/docs/tutorials/rag/
- Chroma 文档：https://docs.trychroma.com/
- PMC OA Bulk 说明：https://www.ncbi.nlm.nih.gov/pmc/tools/openftlist/
- Hugging Face Transformers：https://huggingface.co/docs/transformers/index

---

## 进度跟踪

| 日期 | 完成阶段 | 备注 |
| --- | --- | --- |
| 2026-05-11 (Day 1) | 阶段 0 / 1 / 2.1 ~ 2.2.1 | 概念、硬件、conda 环境、Ollama 安装 + 模型拉取 + 工程内模型管理 |
| 2026-05-12 (Day 2) | 阶段 2.3 ~ 2.5 | 4 题中英文医学问答验证 + 修复 `thinking` 字段 + 量化/Ollama 笔记 |
| 2026-05-13 (Day 3) | 阶段 3 + 阶段 4 | PMC 数据本地全流程（5.1~5.8）+ Chroma smoke test + Chroma 笔记 |
| 2026-05-13 (Day 3) | 阶段 5 | 交付整理（即本次汇报） |
