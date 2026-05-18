"""PMC 数据加载 pipeline（阶段 2）。供 notebook 与脚本复用。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from datasets import Dataset, load_dataset

# --- 阶段 0：字段与口径（与 schedule.md 0.2 / 0.3 对齐）---

EXPECTED_COLUMNS = [
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
]

# 任务书字段 → jsonl 列名（parse_pmc.py 已对齐）
FIELD_MAP = {
    "pub_date": "pub_date",
    "pmid": "pmid",
}

RETRIEVAL_FIELDS = ("title", "abstract")
TOKENIZER_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
TOKENIZER_MAX_LENGTH = 512

# 清洗阈值初稿（最终以阶段 3 实测为准）
ABSTRACT_MISSING_RATE_ALERT = 0.01
SHORT_ABSTRACT_CHAR_THRESHOLD = 50
TITLE_SUSPICIOUS_LEN = 500  # 01 旧 parser 污染阈值；02 修复后应接近 0
BODY_MIN_CHAR_THRESHOLD = 100
XML_RESIDUE_PATTERN = re.compile(r"<[a-zA-Z!/]|&#x[0-9a-fA-F]+;")

# §3 字段完整性分析列
COMPLETENESS_FIELDS = [
    "pmcid",
    "pmid",
    "title",
    "abstract",
    "body",
    "journal",
    "pub_year",
    "pub_date",
]


def resolve_project_dir() -> tuple[str, str]:
    """定位工程根目录（含 任务.txt 的 02 数据处理/）。"""
    env_dir = os.environ.get("PROJECT_DIR")
    if env_dir and os.path.isfile(os.path.join(env_dir, "任务.txt")):
        return env_dir, "环境变量 PROJECT_DIR"

    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.isfile(os.path.join(cur, "任务.txt")):
            return cur, "向上搜索定位到 任务.txt"
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    raise RuntimeError(
        "未能定位工程根目录。请在 VS Code 中打开「02 数据处理」文件夹，\n"
        "或设置环境变量 PROJECT_DIR 指向该目录。"
    )


def setup_paths(project_dir: str) -> dict[str, str]:
    """创建目录并设置 HF 缓存到工程内 caches/。"""
    paths = {
        "project_dir": project_dir,
        "data_dir": os.path.join(project_dir, "data"),
        "data_raw": os.path.join(project_dir, "data", "raw"),
        "data_processed": os.path.join(project_dir, "data", "processed"),
        "outputs_dir": os.path.join(project_dir, "outputs"),
        "figures_dir": os.path.join(project_dir, "outputs", "figures"),
        "tables_dir": os.path.join(project_dir, "outputs", "tables"),
        "samples_dir": os.path.join(project_dir, "outputs", "samples"),
        "caches_dir": os.path.join(project_dir, "caches"),
    }
    paths["hf_cache"] = os.path.join(paths["caches_dir"], "huggingface")
    paths["sample_jsonl"] = os.path.join(paths["data_processed"], "sample.jsonl")

    data_root = os.environ.get("MED_RAG_DATA_ROOT")
    if data_root:
        paths["data_root"] = data_root
        paths["sample_jsonl"] = os.path.join(data_root, "processed", "sample.jsonl")
    else:
        paths["data_root"] = paths["data_dir"]

    for key in (
        "data_raw",
        "data_processed",
        "figures_dir",
        "tables_dir",
        "samples_dir",
        "hf_cache",
    ):
        os.makedirs(paths[key], exist_ok=True)

    datasets_cache = os.path.join(paths["hf_cache"], "datasets")
    os.environ["HF_HOME"] = paths["hf_cache"]
    os.environ["HF_DATASETS_CACHE"] = datasets_cache
    paths["hf_datasets_cache"] = datasets_cache
    return paths


def _derive_row(row: dict[str, Any]) -> dict[str, Any]:
    title = (row.get("title") or "").strip()
    abstract = (row.get("abstract") or "").strip()
    body = (row.get("body") or "").strip()
    retrieval = f"{title}\n{abstract}".strip() if (title or abstract) else ""

    return {
        "has_abstract": bool(abstract),
        "has_body": bool(body),
        "title_char_len": len(title),
        "abstract_char_len": len(abstract),
        "body_char_len": len(body),
        "retrieval_text": retrieval,
        "is_short_abstract": bool(abstract)
        and len(abstract) < SHORT_ABSTRACT_CHAR_THRESHOLD,
    }


def load_pmc_jsonl(
    jsonl_path: str,
    *,
    backend: Literal["datasets", "pandas"] = "datasets",
    add_derived: bool = True,
) -> Dataset | pd.DataFrame:
    """从 JSONL 加载 PMC 样本。"""
    if not os.path.isfile(jsonl_path):
        raise FileNotFoundError(f"找不到数据文件: {jsonl_path}")

    if backend == "pandas":
        df = pd.read_json(jsonl_path, lines=True)
        if add_derived:
            derived = df.apply(
                lambda r: pd.Series(_derive_row(r.to_dict())), axis=1
            )
            df = pd.concat([df, derived], axis=1)
        return df

    cache_dir = os.environ.get("HF_DATASETS_CACHE")
    ds = load_dataset(
        "json",
        data_files=jsonl_path,
        split="train",
        cache_dir=cache_dir,
    )
    if add_derived:
        ds = ds.map(_derive_row, desc="add_derived_features")
    return ds


def validate_schema(ds: Dataset) -> dict[str, Any]:
    """列名、主键唯一性、缺失列检查。"""
    cols = set(ds.column_names)
    missing = [c for c in EXPECTED_COLUMNS if c not in cols]
    extra = sorted(cols - set(EXPECTED_COLUMNS) - {
        "has_abstract",
        "has_body",
        "title_char_len",
        "abstract_char_len",
        "body_char_len",
        "retrieval_text",
        "is_short_abstract",
    })

    pmcids = ds["pmcid"]
    n_dup = len(pmcids) - len(set(pmcids))

    return {
        "n_rows": len(ds),
        "columns": ds.column_names,
        "missing_expected": missing,
        "extra_columns": extra,
        "duplicate_pmcid": n_dup,
        "pmcid_unique": n_dup == 0,
    }


def describe_dataset(ds: Dataset, *, preview_n: int = 2) -> dict[str, Any]:
    """数据集事实摘要，供说明文档「数据集事实」一节引用。"""
    schema = validate_schema(ds)
    n = len(ds)

    def _missing_rate(col: str) -> float | None:
        if col not in ds.column_names:
            return None
        empty = sum(
            1
            for v in ds[col]
            if v is None or (isinstance(v, str) and not v.strip())
        )
        return empty / n if n else 0.0

    facts = {
        **schema,
        "abstract_missing_rate": _missing_rate("abstract"),
        "title_missing_rate": _missing_rate("title"),
        "has_abstract_rate": sum(ds["has_abstract"]) / n if n and "has_abstract" in ds.column_names else None,
        "preview": ds.select(range(min(preview_n, n))),
    }
    return facts


def _is_empty(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    return not str(value).strip()


def field_completeness_table(df: pd.DataFrame) -> pd.DataFrame:
    """各字段非空率 / 缺失率（§3.1）。"""
    n = len(df)
    rows: list[dict[str, Any]] = []
    for col in COMPLETENESS_FIELDS:
        if col not in df.columns:
            rows.append(
                {
                    "field": col,
                    "non_null_count": 0,
                    "missing_count": n,
                    "missing_rate": 1.0,
                    "fill_rate": 0.0,
                }
            )
            continue
        missing = df[col].apply(_is_empty).sum()
        rows.append(
            {
                "field": col,
                "non_null_count": int(n - missing),
                "missing_count": int(missing),
                "missing_rate": round(missing / n, 4) if n else 0.0,
                "fill_rate": round(1 - missing / n, 4) if n else 0.0,
            }
        )
    return pd.DataFrame(rows)


def quality_flags_table(df: pd.DataFrame) -> pd.DataFrame:
    """基础质量标记统计（§3.2）。"""
    n = len(df)
    flags: dict[str, int] = {
        "missing_abstract": int((~df["has_abstract"]).sum()) if "has_abstract" in df else 0,
        "short_abstract": int(df["is_short_abstract"].sum())
        if "is_short_abstract" in df
        else 0,
        "suspicious_long_title": int((df["title_char_len"] > TITLE_SUSPICIOUS_LEN).sum())
        if "title_char_len" in df
        else 0,
        "short_body": int((df["body_char_len"] < BODY_MIN_CHAR_THRESHOLD).sum())
        if "body_char_len" in df
        else 0,
    }

    if "abstract" in df.columns:
        flags["xml_residue_abstract"] = int(
            df["abstract"].astype(str).str.contains(XML_RESIDUE_PATTERN, regex=True).sum()
        )
    if "title" in df.columns:
        flags["xml_residue_title"] = int(
            df["title"].astype(str).str.contains(XML_RESIDUE_PATTERN, regex=True).sum()
        )

    out = pd.DataFrame(
        [{"flag": k, "count": v, "rate": round(v / n, 4) if n else 0.0} for k, v in flags.items()]
    )
    return out


def metadata_summary(df: pd.DataFrame, *, top_journals: int = 10) -> dict[str, Any]:
    """期刊 / 年份 / pmid 覆盖（§3.3）。"""
    n = len(df)
    pmid_ok = 0
    if "pmid" in df.columns:
        pmid_ok = int(df["pmid"].apply(lambda x: not _is_empty(x)).sum())

    journal_nunique = int(df["journal"].nunique()) if "journal" in df.columns else 0
    top_journal = (
        df["journal"].value_counts().head(top_journals).reset_index()
        if "journal" in df.columns
        else pd.DataFrame()
    )

    year_series = pd.to_numeric(df["pub_year"], errors="coerce") if "pub_year" in df.columns else pd.Series(dtype=float)
    year_min = int(year_series.min()) if year_series.notna().any() else None
    year_max = int(year_series.max()) if year_series.notna().any() else None

    from datetime import datetime

    current_year = datetime.now().year
    recent_5y = int((year_series >= current_year - 5).sum()) if year_series.notna().any() else 0

    return {
        "n": n,
        "pmid_fill_count": pmid_ok,
        "pmid_fill_rate": round(pmid_ok / n, 4) if n else 0.0,
        "journal_nunique": journal_nunique,
        "top_journals": top_journal,
        "pub_year_min": year_min,
        "pub_year_max": year_max,
        "pub_year_recent_5y_count": recent_5y,
        "pub_year_recent_5y_rate": round(recent_5y / n, 4) if n else 0.0,
    }


def drop_missing_abstract(df: pd.DataFrame) -> pd.DataFrame:
    """RAG 推荐：丢弃无 abstract 记录。"""
    if "has_abstract" not in df.columns:
        df = df.copy()
        df["has_abstract"] = df["abstract"].apply(lambda x: not _is_empty(x))
    return df[df["has_abstract"]].copy()


def print_config_summary(
    project_dir: str,
    paths: dict[str, str],
) -> None:
    """打印阶段 0 口径，便于核对 notebook 与 schedule 一致。"""
    print("=== 阶段 0：概念与指标约定 ===")
    print(f"PROJECT_DIR     : {project_dir}")
    print(f"DATA_ROOT       : {paths['data_root']}")
    print(f"SAMPLE_JSONL    : {paths['sample_jsonl']}")
    print(f"Tokenizer（统计）: {TOKENIZER_MODEL_ID} (max {TOKENIZER_MAX_LENGTH} tokens)")
    print(f"检索单元字段    : {' + '.join(RETRIEVAL_FIELDS)} → retrieval_text")
    print(f"任务书 pub_date  : 映射为 jsonl 列「{FIELD_MAP['pub_date']}」")
    print(f"任务书 pmid      : jsonl 列「pmid」（由 02 parse_pmc 抽取）")
    print(
        f"清洗阈值（初稿）: abstract 缺失率 > {ABSTRACT_MISSING_RATE_ALERT:.0%} 需决策；"
        f"abstract < {SHORT_ABSTRACT_CHAR_THRESHOLD} 字符标记 is_short_abstract"
    )


__all__ = [
    "ABSTRACT_MISSING_RATE_ALERT",
    "BODY_MIN_CHAR_THRESHOLD",
    "COMPLETENESS_FIELDS",
    "EXPECTED_COLUMNS",
    "FIELD_MAP",
    "RETRIEVAL_FIELDS",
    "SHORT_ABSTRACT_CHAR_THRESHOLD",
    "TITLE_SUSPICIOUS_LEN",
    "TOKENIZER_MAX_LENGTH",
    "TOKENIZER_MODEL_ID",
    "XML_RESIDUE_PATTERN",
    "describe_dataset",
    "drop_missing_abstract",
    "field_completeness_table",
    "load_pmc_jsonl",
    "metadata_summary",
    "print_config_summary",
    "quality_flags_table",
    "resolve_project_dir",
    "setup_paths",
    "validate_schema",
]
