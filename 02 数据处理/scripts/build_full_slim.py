#!/usr/bin/env python
"""全量期：生成 slim JSONL（无 body 正文）+ 丢弃无 abstract 的 pmcid 日志（跨平台 Python 版本）

前置：外接盘已解压 XML，并设置 MED_RAG_DATA_ROOT 或 PMC_XML_ROOT

用法：
    # Windows PowerShell
    $env:MED_RAG_DATA_ROOT = "E:/med-llm-rag-datasets"
    python scripts/build_full_slim.py

    # Unix
    export MED_RAG_DATA_ROOT=/Volumes/Lexar/med-llm-rag-datasets
    python scripts/build_full_slim.py

产出（默认在外接盘 processed/ 下）：
    oa_comm_slim.jsonl
    skipped_no_abstract.txt
"""

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_DIR / "src"))
os.chdir(PROJECT_DIR)
os.environ["PROJECT_DIR"] = str(PROJECT_DIR)


def main():
    med_rag_data_root = os.environ.get("MED_RAG_DATA_ROOT")
    if med_rag_data_root:
        out = str(Path(med_rag_data_root) / "processed" / "oa_comm_slim.jsonl")
        skip_log = str(Path(med_rag_data_root) / "processed" / "skipped_no_abstract.txt")
    else:
        out = str(PROJECT_DIR / "data" / "processed" / "oa_comm_slim.jsonl")
        skip_log = str(PROJECT_DIR / "data" / "processed" / "skipped_no_abstract.txt")

    Path(out).parent.mkdir(parents=True, exist_ok=True)

    sys.argv = [
        "build_jsonl.py",
        "-o", out,
        "--slim",
        "--skip-no-abstract",
        "--skipped-log", skip_log,
    ] + sys.argv[1:]

    from build_jsonl import main as build_main
    build_main()


if __name__ == "__main__":
    main()
