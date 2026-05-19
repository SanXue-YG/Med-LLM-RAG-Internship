"""阶段 4：领域内容理解（任务书 §2）。

notebook §4 调用本模块；分析对象默认 df_clean（有 abstract）。
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from load_pipeline import TOKENIZER_MODEL_ID

IMRAD_PATTERNS: dict[str, re.Pattern[str]] = {
    "background": re.compile(r"\b(background|introduction)\b", re.I),
    "methods": re.compile(
        r"\b(methods?|materials?\s+and\s+methods?|methodology)\b", re.I
    ),
    "results": re.compile(r"\b(results?|findings?)\b", re.I),
    "conclusion": re.compile(
        r"\b(conclusions?|discussion|summary)\b", re.I
    ),
}

ABBREV_PATTERN = re.compile(r"\b[A-Z]{2,6}\b")

STOPWORDS = frozenset(
    "a an the and or of in on for to with by from as at is are was were be been being "
    "this that these those it its we our their has have had not".split()
)

BUCKET_LABELS = ("short", "medium", "long")


def load_tokenizer(model_id: str = TOKENIZER_MODEL_ID):
    """加载 HuggingFace tokenizer（仅计 token，不跑 embedding）。

    统计阶段需要超过 512 的真实 token 数，故放宽 model_max_length，
    避免 transformers 对长摘要误报警（embedding 入库时仍须按 512 截断或切分）。
    """
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_id)
    # 仅用于 EDA 计数；MiniLM 推理上限仍为 512
    tok.model_max_length = 10_000
    return tok


def count_tokens(text: str, tokenizer) -> int:
    """返回全文 token 数（不截断），供长度分布与分桶使用。"""
    if not (text or "").strip():
        return 0
    return len(tokenizer.encode(text, add_special_tokens=False))


def add_abstract_token_len(df: pd.DataFrame, tokenizer) -> pd.DataFrame:
    """为每行 abstract 增加 abstract_token_len 列。"""
    out = df.copy()
    out["abstract_token_len"] = out["abstract"].apply(
        lambda t: count_tokens(str(t) if pd.notna(t) else "", tokenizer)
    )
    return out


def assign_length_bucket(
    df: pd.DataFrame,
    token_col: str = "abstract_token_len",
    quantiles: tuple[float, float] = (0.33, 0.66),
) -> pd.DataFrame:
    """按分位数划分 short / medium / long（列 length_bucket）。"""
    out = df.copy()
    if token_col not in out.columns:
        raise KeyError(f"缺少列 {token_col}，请先 add_abstract_token_len")

    series = out[token_col]
    try:
        out["length_bucket"] = pd.qcut(
            series,
            q=[0, quantiles[0], quantiles[1], 1.0],
            labels=list(BUCKET_LABELS),
            duplicates="drop",
        )
    except ValueError:
        # 分位点重复时退化为 rank 分桶
        ranks = series.rank(method="first")
        out["length_bucket"] = pd.qcut(
            ranks,
            q=3,
            labels=list(BUCKET_LABELS),
            duplicates="drop",
        )
    out["length_bucket"] = out["length_bucket"].astype(str)
    return out


def bucket_thresholds(df: pd.DataFrame, token_col: str = "abstract_token_len") -> dict[str, float]:
    """返回各桶 token 边界（用于说明文档）。"""
    q33, q66 = df[token_col].quantile([0.33, 0.66])
    return {"p33": float(q33), "p66": float(q66)}


def sample_per_bucket(
    df: pd.DataFrame,
    bucket_col: str = "length_bucket",
    n_per_bucket: int = 5,
    random_state: int = 42,
) -> pd.DataFrame:
    """每个 bucket 随机抽 n 篇（不足则全取）。"""
    parts: list[pd.DataFrame] = []
    for bucket in BUCKET_LABELS:
        sub = df[df[bucket_col] == bucket]
        if sub.empty:
            continue
        n = min(n_per_bucket, len(sub))
        parts.append(sub.sample(n=n, random_state=random_state))
    if not parts:
        return df.head(0).copy()
    return pd.concat(parts, ignore_index=True)


def export_stratified_markdown(
    samples: pd.DataFrame,
    out_dir: str | Path,
    *,
    preview_chars: int | None = None,
) -> list[Path]:
    """导出 stratified_{short,medium,long}.md 到 outputs/samples/。

    preview_chars: 默认 ``None`` 输出**完整摘要**（§4.3 人工阅读）；若设正整数则仅截断前 N 字符（极大语料时可省体积）。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    cols_show = [
        "pmcid",
        "pmid",
        "journal",
        "pub_year",
        "abstract_token_len",
        "length_bucket",
        "abstract",
    ]
    cols_show = [c for c in cols_show if c in samples.columns]

    for bucket in BUCKET_LABELS:
        if "length_bucket" in samples.columns:
            sub = samples[samples["length_bucket"] == bucket]
        else:
            sub = samples

        path = out_dir / f"stratified_{bucket}.md"
        lines = [
            f"# 分层抽样：{bucket} 摘要桶",
            "",
            f"共 {len(sub)} 篇（供人工阅读 §4.3）。",
            "",
        ]
        for i, row in sub.iterrows():
            abstract = str(row.get("abstract", "") or "")
            if preview_chars is None or preview_chars <= 0:
                preview = abstract
            else:
                preview = abstract[:preview_chars]
                if len(abstract) > preview_chars:
                    preview += "…"
            lines.append(f"## {row.get('pmcid', i)}")
            lines.append("")
            if "abstract_token_len" in row:
                lines.append(f"- **tokens**: {row['abstract_token_len']}")
            if row.get("pmid"):
                lines.append(f"- **pmid**: {row['pmid']}")
            if row.get("journal"):
                lines.append(f"- **journal**: {row['journal']}")
            if row.get("pub_year"):
                lines.append(f"- **year**: {row['pub_year']}")
            lines.append("")
            lines.append(preview)
            lines.append("")
            lines.append("---")
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        written.append(path)

    return written


def imrad_keyword_rates(df: pd.DataFrame, text_col: str = "abstract") -> pd.DataFrame:
    """各 IMRaD 关键词在摘要中的出现率；另含四键全中比例。"""
    n = len(df)
    if n == 0:
        return pd.DataFrame()

    hits: dict[str, list[bool]] = {k: [] for k in IMRAD_PATTERNS}
    all_four: list[bool] = []

    for text in df[text_col].astype(str):
        flags = {k: bool(p.search(text)) for k, p in IMRAD_PATTERNS.items()}
        for k, v in flags.items():
            hits[k].append(v)
        all_four.append(all(flags.values()))

    rows = [
        {
            "section": k,
            "match_count": sum(hits[k]),
            "match_rate": round(sum(hits[k]) / n, 4),
        }
        for k in IMRAD_PATTERNS
    ]
    rows.append(
        {
            "section": "all_four",
            "match_count": sum(all_four),
            "match_rate": round(sum(all_four) / n, 4),
        }
    )
    return pd.DataFrame(rows)


def abbreviation_stats(df: pd.DataFrame, text_col: str = "abstract") -> pd.DataFrame:
    """每篇缩写个数与密度（缩写数 / 词数）。"""
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        text = str(row.get(text_col, "") or "")
        words = re.findall(r"[A-Za-z]+", text)
        n_words = max(len(words), 1)
        abbrevs = ABBREV_PATTERN.findall(text)
        n_abbrev = len(abbrevs)
        rows.append(
            {
                "pmcid": row.get("pmcid", ""),
                "abbrev_count": n_abbrev,
                "word_count": len(words),
                "abbrev_per_100_words": round(100 * n_abbrev / n_words, 2),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    summary = pd.DataFrame(
        [
            {
                "pmcid": "__summary__",
                "abbrev_count": int(out["abbrev_count"].mean()),
                "word_count": int(out["word_count"].mean()),
                "abbrev_per_100_words": round(out["abbrev_per_100_words"].mean(), 2),
            }
        ]
    )
    return pd.concat([out, summary], ignore_index=True)


def top_terms(
    df: pd.DataFrame,
    text_col: str = "abstract",
    top_n: int = 30,
) -> pd.Series:
    """合并摘要后的高频词 Top-N（过滤停用词与纯数字）。"""
    counter: Counter[str] = Counter()
    for text in df[text_col].astype(str):
        for word in re.findall(r"[A-Za-z]{3,}", text.lower()):
            if word in STOPWORDS:
                continue
            counter[word] += 1
    return pd.Series(dict(counter.most_common(top_n)), name="count")


def run_domain_pipeline(
    df_clean: pd.DataFrame,
    *,
    samples_dir: str | Path,
    tables_dir: str | Path | None = None,
    n_per_bucket: int = 5,
    model_id: str = TOKENIZER_MODEL_ID,
) -> dict[str, Any]:
    """一键跑 §4.1 + §4.2，返回中间结果供 notebook 展示。"""
    tokenizer = load_tokenizer(model_id)
    df4 = assign_length_bucket(add_abstract_token_len(df_clean, tokenizer))
    samples = sample_per_bucket(df4, n_per_bucket=n_per_bucket)
    md_paths = export_stratified_markdown(samples, samples_dir)

    imrad_df = imrad_keyword_rates(df_clean)
    abbrev_df = abbreviation_stats(df_clean)
    top30 = top_terms(df_clean, top_n=30)

    if tables_dir:
        tables_dir = Path(tables_dir)
        tables_dir.mkdir(parents=True, exist_ok=True)
        imrad_df.to_csv(tables_dir / "imrad_keyword_rate.csv", index=False)
        abbrev_df.to_csv(tables_dir / "abbrev_density.csv", index=False)
        top30.reset_index().rename(columns={"index": "term"}).to_csv(
            tables_dir / "abstract_top_terms.csv", index=False
        )

    return {
        "df4": df4,
        "samples": samples,
        "md_paths": md_paths,
        "imrad_df": imrad_df,
        "abbrev_df": abbrev_df,
        "top30": top30,
        "thresholds": bucket_thresholds(df4),
    }


__all__ = [
    "ABBREV_PATTERN",
    "BUCKET_LABELS",
    "IMRAD_PATTERNS",
    "TOKENIZER_MODEL_ID",
    "abbreviation_stats",
    "add_abstract_token_len",
    "assign_length_bucket",
    "bucket_thresholds",
    "count_tokens",
    "export_stratified_markdown",
    "imrad_keyword_rates",
    "load_tokenizer",
    "run_domain_pipeline",
    "sample_per_bucket",
    "top_terms",
]
