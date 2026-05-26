#!/usr/bin/env zsh
# 扫描 XML 目录，生成 pmcid → 相对路径 索引（全量期建库前执行一次）
#
# 用法：
#   ./scripts/build_pmcid_index.sh
#   ./scripts/build_pmcid_index.sh --xml-root /Volumes/盘/med-rag-pmc/extracted
#   ./scripts/build_pmcid_index.sh -o /Volumes/盘/med-rag-pmc/processed/pmcid_index.jsonl
#
# 环境变量：PMC_XML_ROOT、MED_RAG_DATA_ROOT（同 build_jsonl.sh）

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PY="/opt/miniconda3/envs/med-rag-verify/bin/python"

cd "${PROJECT_DIR}"
export PROJECT_DIR="${PROJECT_DIR}"

XML_ROOT="${PMC_XML_ROOT:-}"
OUT="${1:-data/processed/pmcid_index.jsonl}"

if [[ -n "${MED_RAG_DATA_ROOT}" ]]; then
  [[ -z "${XML_ROOT}" ]] && XML_ROOT="${MED_RAG_DATA_ROOT}/extracted"
  [[ "${OUT}" != /* ]] && OUT="${MED_RAG_DATA_ROOT}/processed/pmcid_index.jsonl"
fi

if [[ -z "${XML_ROOT}" ]]; then
  for c in "${PROJECT_DIR}/data/raw/extracted" "${PROJECT_DIR}/../01 验证模型/data/raw/extracted"; do
    if [[ -d "${c}" ]]; then
      XML_ROOT="${c}"
      break
    fi
  done
fi

if [[ ! -d "${XML_ROOT}" ]]; then
  echo "找不到 XML 目录，请设置 PMC_XML_ROOT" >&2
  exit 1
fi

mkdir -p "$(dirname "${OUT}")"

"${PY}" -c "
from pathlib import Path
import sys
sys.path.insert(0, 'src')
from pmc_index import build_pmcid_index

stats = build_pmcid_index('${XML_ROOT}', '${OUT}')
print(f'Indexed: {stats[\"indexed\"]} → ${OUT}')
"
