#!/usr/bin/env python
"""从 PMC XML 批量生成 JSONL（跨平台 Python 版本）

用法示例：
    python scripts/build_jsonl.py
    python scripts/build_jsonl.py --limit 100
    python scripts/build_jsonl.py --pmcids-from data/processed/sample.jsonl.bak01
    python scripts/build_jsonl.py --slim --skip-no-abstract -o data/processed/oa_comm_slim.jsonl

环境变量：
    PMC_XML_ROOT      — XML 解压根目录（全量期指向外接盘 extracted/）
    MED_RAG_DATA_ROOT — 全量数据根（含 extracted/、processed/）
    MED_RAG_JSONL     — 分析 notebook 加载的 jsonl 路径
"""

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_DIR / "src"))
os.chdir(PROJECT_DIR)
os.environ["PROJECT_DIR"] = str(PROJECT_DIR)

if __name__ == "__main__":
    from build_jsonl import main
    main()
