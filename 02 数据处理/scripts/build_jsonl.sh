#!/usr/bin/env zsh
# 从 PMC XML 批量生成 JSONL（02 数据处理标准入口，不依赖 01 notebook）
#
# 用法示例：
#   ./scripts/build_jsonl.sh                          # 验证期：自动找 XML → sample.jsonl
#   ./scripts/build_jsonl.sh --limit 100
#   ./scripts/build_jsonl.sh --pmcids-from data/processed/sample.jsonl.bak01
#   ./scripts/build_full_slim.sh                      # 全量期：slim + 丢弃无 abstract（见该脚本）
#   ./scripts/build_jsonl.sh --slim --skip-no-abstract -o data/processed/oa_comm_slim.jsonl
#
# 环境变量：
#   PMC_XML_ROOT      — XML 解压根目录（全量期指向外接盘 extracted/）
#   MED_RAG_DATA_ROOT — 全量数据根（含 extracted/、processed/）
#   MED_RAG_JSONL     — 分析 notebook 加载的 jsonl 路径（全量期指向 oa_comm_slim.jsonl）

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY="/opt/miniconda3/envs/med-rag-verify/bin/python"

cd "${PROJECT_DIR}"
export PROJECT_DIR="${PROJECT_DIR}"

exec "${PY}" "${PROJECT_DIR}/src/build_jsonl.py" "$@"
