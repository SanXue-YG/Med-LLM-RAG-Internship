#!/usr/bin/env zsh
# Ollama 启动脚本（按需启动，非重启自动启动后台服务）
#
# 用法：在终端中执行
#   ./start_ollama.sh
# 或：
#   bash start_ollama.sh
#
# 启动后保持窗口不关，按 Ctrl+C 停止服务。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export OLLAMA_MODELS="${SCRIPT_DIR}/ollama_models"

echo "============================================"
echo "  Ollama 启动 (工程内模型存储模式)"
echo "============================================"
echo "OLLAMA_MODELS: ${OLLAMA_MODELS}"
echo "OLLAMA_HOST  : http://127.0.0.1:11434"
echo ""
echo "提示：保持本窗口不关，按 Ctrl+C 停止服务"
echo "============================================"
echo ""

exec ollama serve
