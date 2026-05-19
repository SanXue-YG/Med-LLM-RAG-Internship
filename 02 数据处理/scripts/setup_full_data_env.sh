#!/usr/bin/env zsh
# 全量期外接盘环境变量（Lexar · 2026-05-19 已验证可写）
# 用法：cd "02 数据处理" && source ./scripts/setup_full_data_env.sh

export MED_RAG_DATA_ROOT=/Volumes/Lexar/med-llm-rag-datasets
export PMC_XML_ROOT="${MED_RAG_DATA_ROOT}/extracted"
export MED_RAG_JSONL="${MED_RAG_DATA_ROOT}/processed/oa_comm_slim.jsonl"

if [[ ! -d "${MED_RAG_DATA_ROOT}" ]]; then
  echo "错误: 外接盘未挂载 — ${MED_RAG_DATA_ROOT}" >&2
  return 1 2>/dev/null || exit 1
fi

mkdir -p "${MED_RAG_DATA_ROOT}"/{raw,extracted,processed/stats}
echo "MED_RAG_DATA_ROOT=${MED_RAG_DATA_ROOT}"
echo "PMC_XML_ROOT=${PMC_XML_ROOT}"
echo "MED_RAG_JSONL=${MED_RAG_JSONL}"
