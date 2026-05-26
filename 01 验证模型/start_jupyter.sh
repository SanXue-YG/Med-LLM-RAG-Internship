#!/usr/bin/env zsh
# Jupyter Server 启动脚本
#
# 作用：
#   1. 把 HuggingFace / PyTorch / Transformers 等缓存重定向到工程内 caches/
#   2. 使用 med-rag-verify 环境的 Jupyter 启动 server，对外端口 8888
#
# 用法：
#   ./start_jupyter.sh
#
# 启动后保持窗口不关，Cursor 通过「Existing Jupyter Server」连接。
# Ctrl+C 停止。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 工程根目录显式导出，notebook 中直接读取，不依赖 CWD 与 __file__
export PROJECT_DIR="${SCRIPT_DIR}"

# 所有可能产生大数据的缓存目录都拉到工程内
export HF_HOME="${SCRIPT_DIR}/caches/huggingface"
export TORCH_HOME="${SCRIPT_DIR}/caches/torch"
export TRANSFORMERS_CACHE="${SCRIPT_DIR}/caches/transformers"
export HF_DATASETS_CACHE="${SCRIPT_DIR}/caches/huggingface/datasets"

mkdir -p "${HF_HOME}" "${TORCH_HOME}" "${TRANSFORMERS_CACHE}" "${HF_DATASETS_CACHE}"

# 把 CWD 切到工程根目录，让 jupyter 启动时显示的根路径也对
cd "${SCRIPT_DIR}"

CONDA_ENV_PY="/opt/miniconda3/envs/med-rag-verify/bin/python"
JUPYTER_BIN="/opt/miniconda3/envs/med-rag-verify/bin/jupyter"

if [[ ! -x "${JUPYTER_BIN}" ]]; then
    echo "ERROR: 找不到 jupyter，预期路径: ${JUPYTER_BIN}"
    echo "请确认 med-rag-verify 环境是否还存在: conda env list"
    exit 1
fi

echo "============================================"
echo "  Jupyter Server (工程内缓存模式)"
echo "============================================"
echo "PROJECT_DIR       : ${PROJECT_DIR}"
echo "HF_HOME           : ${HF_HOME}"
echo "TORCH_HOME        : ${TORCH_HOME}"
echo "TRANSFORMERS_CACHE: ${TRANSFORMERS_CACHE}"
echo "Python            : ${CONDA_ENV_PY}"
echo "CWD               : $(pwd)"
echo ""
echo "提示：保持本窗口不关，按 Ctrl+C 停止"
echo "在 Cursor 中：选择其他内核 → Existing Jupyter Server → 粘贴下方 URL"
echo "============================================"
echo ""

exec "${JUPYTER_BIN}" notebook --no-browser --port=8888
