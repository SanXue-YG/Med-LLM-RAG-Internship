"""批量将 PMC XML 目录解析为 JSONL（验证期 / 全量期通用）。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from tqdm import tqdm

from parse_pmc import JSONL_FIELDS, parse_pmc_xml


def resolve_xml_root(project_dir: str, xml_root: str | None = None) -> str:
    """解析 XML 根目录：参数 > 环境变量 > 本工程 data/raw/extracted > 01 解压目录。"""
    candidates: list[str] = []
    if xml_root:
        candidates.append(xml_root)
    env = os.environ.get("PMC_XML_ROOT")
    if env:
        candidates.append(env)
    candidates.extend(
        [
            os.path.join(project_dir, "data", "raw", "extracted"),
            os.path.join(
                project_dir, "..", "01 验证模型", "data", "raw", "extracted"
            ),
        ]
    )
    if os.environ.get("MED_RAG_DATA_ROOT"):
        candidates.insert(
            0,
            os.path.join(os.environ["MED_RAG_DATA_ROOT"], "extracted"),
        )

    for path in candidates:
        abspath = os.path.abspath(path)
        if os.path.isdir(abspath):
            return abspath
    raise FileNotFoundError(
        "找不到 XML 目录。请指定 --xml-root 或设置 PMC_XML_ROOT / "
        "将解压后的 XML 放到 data/raw/extracted/"
    )


def iter_xml_files(xml_root: str, limit: int | None = None) -> list[Path]:
    files = sorted(Path(xml_root).rglob("*.xml"))
    if limit is not None and limit > 0:
        files = files[:limit]
    return files


def build_jsonl(
    xml_root: str,
    output_path: str,
    *,
    limit: int | None = None,
    pmcid_filter: set[str] | None = None,
) -> dict[str, int]:
    """
    扫描 xml_root 下 XML，写入 JSONL。

    pmcid_filter: 若提供，仅保留这些 pmcid（用于对齐既有 100 篇样本）。
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    stats = {"ok": 0, "skipped": 0, "failed": 0}
    files = iter_xml_files(xml_root, limit=None if pmcid_filter else limit)

    with open(output_path, "w", encoding="utf-8") as fout:
        for xml_path in tqdm(files, desc="parse_xml"):
            try:
                rec = parse_pmc_xml(xml_path)
            except Exception:
                stats["failed"] += 1
                continue

            pmcid = (rec.get("pmcid") or "").strip()
            if not pmcid:
                stats["skipped"] += 1
                continue
            if pmcid_filter and pmcid not in pmcid_filter:
                continue

            fout.write(
                json.dumps(
                    {k: rec[k] for k in JSONL_FIELDS},
                    ensure_ascii=False,
                )
                + "\n"
            )
            stats["ok"] += 1

            if pmcid_filter and stats["ok"] >= len(pmcid_filter):
                break
            if limit and not pmcid_filter and stats["ok"] >= limit:
                break

    return stats


def load_pmcid_set(jsonl_path: str) -> set[str]:
    ids: set[str] = set()
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ids.add(json.loads(line)["pmcid"])
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PMC XML → JSONL（02 数据处理 build pipeline）"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="data/processed/sample.jsonl",
        help="输出 JSONL 路径（相对工程根或绝对路径）",
    )
    parser.add_argument(
        "--xml-root",
        default=None,
        help="XML 解压根目录（默认自动探测）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="最多写入篇数（未指定 --pmcids-from 时生效）",
    )
    parser.add_argument(
        "--pmcids-from",
        default=None,
        help="从已有 jsonl 读取 pmcid 列表，仅重解析这些篇（用于对齐样本）",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="02 数据处理工程根目录（默认向上找 任务.txt）",
    )
    args = parser.parse_args()

    project_dir = args.project_dir
    if not project_dir:
        cur = os.path.abspath(os.getcwd())
        while True:
            if os.path.isfile(os.path.join(cur, "任务.txt")):
                project_dir = cur
                break
            parent = os.path.dirname(cur)
            if parent == cur:
                raise SystemExit("无法定位工程根目录，请传 --project-dir")
            cur = parent

    xml_root = resolve_xml_root(project_dir, args.xml_root)
    output = args.output
    if not os.path.isabs(output):
        output = os.path.join(project_dir, output)

    pmcid_filter = None
    if args.pmcids_from:
        pmcid_path = args.pmcids_from
        if not os.path.isabs(pmcid_path):
            pmcid_path = os.path.join(project_dir, pmcid_path)
        pmcid_filter = load_pmcid_set(pmcid_path)

    print(f"XML root : {xml_root}")
    print(f"Output   : {output}")
    if pmcid_filter:
        print(f"PMCIDs   : {len(pmcid_filter)} from {args.pmcids_from}")
    elif args.limit:
        print(f"Limit    : {args.limit}")

    stats = build_jsonl(
        xml_root,
        output,
        limit=args.limit,
        pmcid_filter=pmcid_filter,
    )
    print(f"Done: ok={stats['ok']} skipped={stats['skipped']} failed={stats['failed']}")


if __name__ == "__main__":
    main()
