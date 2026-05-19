"""阶段 5：文本特征量化（任务书 §3）— token 长度与分位数。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from domain_analysis import count_tokens, load_tokenizer
from load_pipeline import TOKENIZER_MAX_LENGTH, TOKENIZER_MODEL_ID

TOKEN_LEN_FIELDS = (
    ("title", "title_token_len"),
    ("abstract", "abstract_token_len"),
    ("title+abstract", "retrieval_token_len"),
    ("body", "body_token_len"),
)


def _retrieval_text(row: pd.Series) -> str:
    t = str(row.get("title", "") or "").strip()
    a = str(row.get("abstract", "") or "").strip()
    if t and a:
        return f"{t}\n{a}"
    return t or a


def add_all_token_lens(df: pd.DataFrame, tokenizer) -> pd.DataFrame:
    """为 title / abstract / title+abstract / body 增加 *_token_len 列。"""
    out = df.copy()

    def tok(s: Any) -> int:
        return count_tokens(str(s) if pd.notna(s) else "", tokenizer)

    out["title_token_len"] = out["title"].apply(tok)
    out["abstract_token_len"] = out["abstract"].apply(tok)
    out["retrieval_token_len"] = out.apply(_retrieval_text, axis=1).map(tok)
    if "body" in out.columns:
        out["body_token_len"] = out["body"].apply(tok)
    else:
        out["body_token_len"] = 0

    return out


def token_percentile_table(df: pd.DataFrame) -> pd.DataFrame:
    """均值 + P50/P75/P95/P99/max（与 schedule §5.1 对齐）。"""
    quantiles = [0.0, 0.5, 0.75, 0.95, 0.99, 1.0]
    qnames = ["min", "p50", "p75", "p95", "p99", "max"]
    rows: list[dict[str, Any]] = []

    for label, col in TOKEN_LEN_FIELDS:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            continue
        qv = s.quantile(quantiles)
        row: dict[str, Any] = {
            "field": label,
            "n": int(len(s)),
            "mean": round(float(s.mean()), 2),
        }
        for i, name in enumerate(qnames):
            row[name] = round(float(qv.iloc[i]), 2)
        rows.append(row)

    return pd.DataFrame(rows)


def over_limit_rate(df: pd.DataFrame, col: str, limit: int = TOKENIZER_MAX_LENGTH) -> float:
    if col not in df.columns:
        return 0.0
    s = df[col].dropna()
    if len(s) == 0:
        return 0.0
    return float((s > limit).sum() / len(s))


def plot_token_ecdf(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    cols: tuple[tuple[str, str], ...] = (
        ("abstract_token_len", "abstract"),
        ("retrieval_token_len", "title + abstract"),
    ),
) -> Path:
    """ECDF + 512 参考线。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, len(cols), figsize=(5 * len(cols), 4), squeeze=False)
    ax_flat = axes.ravel()

    for ax, (col, title) in zip(ax_flat, cols):
        if col not in df.columns:
            ax.set_visible(False)
            continue
        s = np.sort(df[col].dropna().astype(float).values)
        if len(s) == 0:
            continue
        y = np.arange(1, len(s) + 1) / len(s)
        ax.plot(s, y, drawstyle="steps-post", label="ECDF")
        ax.axvline(TOKENIZER_MAX_LENGTH, color="C3", linestyle="--", label=f"{TOKENIZER_MAX_LENGTH} (MiniLM max)")
        ax.set_xlabel("tokens")
        ax.set_ylabel("CDF")
        ax.set_title(title)
        ax.legend(loc="lower right", fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=0)

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output_path


def embedding_fit_summary(df: pd.DataFrame, *, limit: int = TOKENIZER_MAX_LENGTH) -> dict[str, Any]:
    """与 §5.2 对照：检索单元是否多数可放入 512。"""
    r = "retrieval_token_len"
    a = "abstract_token_len"
    out: dict[str, Any] = {"limit": limit}
    if r in df.columns:
        s = df[r].dropna()
        out["retrieval_p95"] = float(s.quantile(0.95)) if len(s) else None
        out["retrieval_p99"] = float(s.quantile(0.99)) if len(s) else None
        out["retrieval_over_limit_rate"] = over_limit_rate(df, r, limit)
    if a in df.columns:
        s = df[a].dropna()
        out["abstract_p95"] = float(s.quantile(0.95)) if len(s) else None
        out["abstract_over_limit_rate"] = over_limit_rate(df, a, limit)
    return out


def run_stage5_token_report(
    df: pd.DataFrame,
    tokenizer=None,
    *,
    tables_dir: str | Path,
    figures_dir: str | Path,
    model_id: str = TOKENIZER_MODEL_ID,
) -> dict[str, Any]:
    """§5 一键：加列 → 分位数表 → ECDF 图 → 512 对照摘要。"""
    tables_dir = Path(tables_dir)
    figures_dir = Path(figures_dir)
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    if tokenizer is None:
        tokenizer = load_tokenizer(model_id)

    df5 = add_all_token_lens(df, tokenizer)
    pct = token_percentile_table(df5)
    pct_path = tables_dir / "token_percentiles.csv"
    pct.to_csv(pct_path, index=False)

    fig_path = figures_dir / "token_dist_abstract.png"
    plot_token_ecdf(df5, fig_path)

    fit = embedding_fit_summary(df5)
    return {
        "df5": df5,
        "percentiles": pct,
        "percentiles_path": pct_path,
        "figure_path": fig_path,
        "embedding_fit": fit,
    }


__all__ = [
    "TOKEN_LEN_FIELDS",
    "add_all_token_lens",
    "embedding_fit_summary",
    "over_limit_rate",
    "plot_token_ecdf",
    "run_stage5_token_report",
    "token_percentile_table",
]
