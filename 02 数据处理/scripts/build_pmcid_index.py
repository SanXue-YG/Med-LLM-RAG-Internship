#!/usr/bin/env python
"""扫描 XML 目录，生成 pmcid → 相对路径 索引（跨平台 Python 版本）

用法：
    python scripts/build_pmcid_index.py
    python scripts/build_pmcid_index.py --xml-root E:/med-llm-rag-datasets/extracted
    python scripts/build_pmcid_index.py -o E:/med-llm-rag-datasets/processed/pmcid_index.jsonl

环境变量：PMC_XML_ROOT、MED_RAG_DATA_ROOT
"""

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_DIR / "src"))
os.chdir(PROJECT_DIR)
os.environ["PROJECT_DIR"] = str(PROJECT_DIR)


def find_xml_root() -> str | None:
    """自动探测 XML 目录"""
    pmc_xml_root = os.environ.get("PMC_XML_ROOT")
    if pmc_xml_root and Path(pmc_xml_root).is_dir():
        return pmc_xml_root

    med_rag_data_root = os.environ.get("MED_RAG_DATA_ROOT")
    if med_rag_data_root:
        extracted = Path(med_rag_data_root) / "extracted"
        if extracted.is_dir():
            return str(extracted)

    candidates = [
        PROJECT_DIR / "data" / "raw" / "extracted",
        PROJECT_DIR.parent / "01 验证模型" / "data" / "raw" / "extracted",
    ]
    for c in candidates:
        if c.is_dir():
            return str(c)
    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build pmcid index from XML files")
    parser.add_argument("--xml-root", help="XML directory root")
    parser.add_argument("-o", "--output", help="Output jsonl path")
    args = parser.parse_args()

    xml_root = args.xml_root or find_xml_root()
    if not xml_root or not Path(xml_root).is_dir():
        print("找不到 XML 目录，请设置 PMC_XML_ROOT 环境变量", file=sys.stderr)
        sys.exit(1)

    med_rag_data_root = os.environ.get("MED_RAG_DATA_ROOT")
    if args.output:
        out = args.output
    elif med_rag_data_root:
        out = str(Path(med_rag_data_root) / "processed" / "pmcid_index.jsonl")
    else:
        out = str(PROJECT_DIR / "data" / "processed" / "pmcid_index.jsonl")

    Path(out).parent.mkdir(parents=True, exist_ok=True)

    from pmc_index import build_pmcid_index
    stats = build_pmcid_index(xml_root, out)
    print(f"Indexed: {stats['indexed']} → {out}")


if __name__ == "__main__":
    main()
