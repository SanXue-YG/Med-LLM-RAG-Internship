"""PMC pmcid ↔ XML 路径索引与按需读取 body（全量期）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from parse_pmc import normalize_pmcid, parse_pmc_xml, resolve_pmc_xml_path


def build_pmcid_index(
    xml_root: str | Path,
    output_path: str | Path,
    *,
    relative_paths: bool = True,
) -> dict[str, int]:
    """
    扫描 xml_root 下全部 XML，写入 pmcid 索引 JSONL（每行 pmcid + path）。

    全量建库前执行一次；后续用 resolve_xml_path_from_index 或 resolve_pmc_xml_path 定位文件。
    """
    xml_root = Path(xml_root)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {"indexed": 0, "skipped": 0}
    with open(output_path, "w", encoding="utf-8") as fout:
        for xml_path in sorted(xml_root.rglob("*.xml")):
            pmcid = normalize_pmcid(xml_path.stem)
            if not pmcid:
                stats["skipped"] += 1
                continue
            path_str = (
                str(xml_path.relative_to(xml_root))
                if relative_paths
                else str(xml_path.resolve())
            )
            fout.write(
                json.dumps({"pmcid": pmcid, "path": path_str}, ensure_ascii=False)
                + "\n"
            )
            stats["indexed"] += 1
    return stats


def load_pmcid_index(index_path: str | Path) -> dict[str, str]:
    """加载索引 JSONL 为 dict[pmcid -> path]。"""
    index: dict[str, str] = {}
    with open(index_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            pid = normalize_pmcid(row.get("pmcid", ""))
            if pid and row.get("path"):
                index[pid] = row["path"]
    return index


def resolve_xml_path_from_index(
    pmcid: str,
    xml_root: str | Path,
    index: dict[str, str],
) -> Path | None:
    """优先用预建索引，否则回退 pmcid 桶路径规则。"""
    pid = normalize_pmcid(pmcid)
    rel = index.get(pid)
    if rel:
        return Path(xml_root) / rel
    candidate = resolve_pmc_xml_path(pid, xml_root)
    return candidate if candidate.is_file() else None


def load_body_for_pmcid(
    pmcid: str,
    *,
    xml_root: str | Path | None = None,
    index_path: str | Path | None = None,
    index: dict[str, str] | None = None,
) -> str:
    """按需从 XML 读取 body 全文（用于 body token 抽样 / 分割 demo）。"""
    if xml_root is None:
        xml_root = os.environ.get("PMC_XML_ROOT") or os.environ.get(
            "MED_RAG_DATA_ROOT", ""
        )
        if xml_root and os.path.isdir(os.path.join(str(xml_root), "extracted")):
            xml_root = os.path.join(str(xml_root), "extracted")
        if not xml_root or not os.path.isdir(xml_root):
            raise FileNotFoundError(
                "请设置 PMC_XML_ROOT 或 MED_RAG_DATA_ROOT/extracted"
            )

    xml_root = Path(xml_root)
    idx = index
    if idx is None and index_path:
        idx = load_pmcid_index(index_path)

    if idx is not None:
        path = resolve_xml_path_from_index(pmcid, xml_root, idx)
    else:
        path = resolve_pmc_xml_path(pmcid, xml_root)
        if not path.is_file():
            path = None

    if path is None or not path.is_file():
        raise FileNotFoundError(f"找不到 XML: pmcid={pmcid}")

    rec = parse_pmc_xml(path)
    return (rec.get("body") or "").strip()


__all__ = [
    "build_pmcid_index",
    "load_body_for_pmcid",
    "load_pmcid_index",
    "resolve_xml_path_from_index",
]
