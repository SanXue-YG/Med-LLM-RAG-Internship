"""PMC JATS XML → 结构化字段（02 数据处理标准解析器）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lxml import etree

# jsonl 输出列顺序
JSONL_FIELDS = (
    "pmcid",
    "pmid",
    "title",
    "abstract",
    "body",
    "journal",
    "pub_year",
    "pub_date",
    "n_chars_abstract",
    "n_chars_body",
)


def _node_text(node: etree._Element, sep: str = " ") -> str:
    return sep.join(t.strip() for t in node.itertext() if t and t.strip())


def _first_text(root: etree._Element, xpath: str) -> str:
    nodes = root.xpath(xpath)
    if not nodes:
        return ""
    node = nodes[0]
    if isinstance(node, str):
        return node.strip()
    return _node_text(node)


def _join_text(root: etree._Element, xpath: str, sep: str = "\n") -> str:
    nodes = root.xpath(xpath)
    parts = []
    for node in nodes:
        if isinstance(node, str):
            text = node.strip()
        else:
            text = _node_text(node)
        if text:
            parts.append(text)
    return sep.join(parts)


def _extract_pub_year(root: etree._Element) -> str:
    """取 front 内文章级出版年（优先 epub，其次 ppub，再任意 pub-date）。"""
    for xpath in (
        "//front//pub-date[@pub-type='epub']/year",
        "//front//pub-date[@pub-type='ppub']/year",
        "//front//pub-date[@pub-type='collection']/year",
        "(//front//pub-date/year)[1]",
    ):
        year = _first_text(root, xpath)
        if year:
            m = re.search(r"\d{4}", year)
            if m:
                return m.group(0)
    return ""


def _extract_pub_date(root: etree._Element) -> str:
    """从 front 内 pub-date 拼 ISO 日期（YYYY-MM-DD 或 YYYY-MM 或 YYYY）。"""
    for xpath in (
        "//front//pub-date[@pub-type='epub']",
        "//front//pub-date[@pub-type='ppub']",
        "(//front//pub-date)[1]",
    ):
        nodes = root.xpath(xpath)
        if not nodes:
            continue
        pd = nodes[0]
        y = _first_text(pd, "year") or ""
        mo = _first_text(pd, "month") or ""
        d = _first_text(pd, "day") or ""
        ym = re.search(r"\d{4}", y)
        if not ym:
            continue
        year = ym.group(0)
        if mo and d:
            return f"{year}-{mo.zfill(2)}-{d.zfill(2)}"
        if mo:
            return f"{year}-{mo.zfill(2)}"
        return year
    return ""


def parse_pmc_xml(xml_path: str | Path) -> dict[str, Any]:
    """解析单个 PMC JATS XML，返回核心字段 dict。"""
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    pmcid = _first_text(root, "//front//article-id[@pub-id-type='pmc']")
    pmid = _first_text(root, "//front//article-id[@pub-id-type='pmid']")
    title = _first_text(root, "//front//title-group/article-title[1]")
    journal = _first_text(root, "//front//journal-title")
    pub_year = _extract_pub_year(root)
    pub_date = _extract_pub_date(root)

    # 摘要：限定 front，覆盖 structured / plain abstract
    abstract = _join_text(root, "//front//abstract[not(@abstract-type='graphical')]//p")
    if not abstract.strip():
        abstract = _join_text(root, "//front//abstract[not(@abstract-type='graphical')]")

    body = _join_text(root, "//body//p")

    rec = {
        "pmcid": pmcid,
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "body": body,
        "journal": journal,
        "pub_year": str(pub_year) if pub_year else "",
        "pub_date": str(pub_date) if pub_date else "",
        "n_chars_abstract": len(abstract),
        "n_chars_body": len(body),
    }
    return rec
