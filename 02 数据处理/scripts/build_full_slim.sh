#!/usr/bin/env zsh
# 全量期：生成 slim JSONL（无 body 正文）+ 丢弃无 abstract 的 pmcid 日志
#
# 前置：外接盘已解压 XML，并设置 MED_RAG_DATA_ROOT 或 PMC_XML_ROOT
#
# 用法：
#   export MED_RAG_DATA_ROOT=/Volumes/<盘>/med-rag-pmc
#   ./scripts/build_full_slim.sh
#
# 产出（默认在外接盘 processed/ 下）：
#   oa_comm_slim.jsonl
#   skipped_no_abstract.txt

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -n "${MED_RAG_DATA_ROOT}" ]]; then
  OUT="${MED_RAG_DATA_ROOT}/processed/oa_comm_slim.jsonl"
  SKIP_LOG="${MED_RAG_DATA_ROOT}/processed/skipped_no_abstract.txt"
else
  OUT="${PROJECT_DIR}/data/processed/oa_comm_slim.jsonl"
  SKIP_LOG="${PROJECT_DIR}/data/processed/skipped_no_abstract.txt"
fi

exec "${SCRIPT_DIR}/build_jsonl.sh" \
  -o "${OUT}" \
  --slim \
  --skip-no-abstract \
  --skipped-log "${SKIP_LOG}" \
  "$@"
