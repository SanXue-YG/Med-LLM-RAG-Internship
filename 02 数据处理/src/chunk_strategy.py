"""阶段 6：文本分割策略（任务书 §4）— 定稿参数与切块 demo。

入库 pipeline（未来全量 / RAG）应调用本模块，而非在查询时数 token。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from domain_analysis import count_tokens, load_tokenizer
from load_pipeline import (
    SHORT_ABSTRACT_CHAR_THRESHOLD,
    TOKENIZER_MAX_LENGTH,
    TOKENIZER_MODEL_ID,
    drop_missing_abstract,
)

# --- 定稿参数（验证期 97 篇 + 阶段 5 分位数支撑）---

RETRIEVAL_UNIT = "title+abstract"
RETRIEVAL_TOKEN_LIMIT = TOKENIZER_MAX_LENGTH  # 512，与 MiniLM 对齐

# 长尾 title+abstract（~14% >512）：滑动窗口
RETRIEVAL_CHUNK_SIZE = 400
RETRIEVAL_CHUNK_OVERLAP = 80

# 正文 body（100% >512）：单独 pipeline，块可略大以减 chunk 数
BODY_CHUNK_SIZE = 512
BODY_CHUNK_OVERLAP = 80

# 字符粗筛：避免每篇都 encode；约 4 字符/token，512 token ≈ 2048 字符
RETRIEVAL_CHAR_SAFE = 1800


@dataclass
class ChunkRecord:
    """单条待 embedding 的 chunk。"""

    pmcid: str
    chunk_index: int
    chunk_count: int
    text: str
    token_len: int
    source_field: str  # retrieval | body
    strategy: str  # single | sliding_window


@dataclass
class ChunkStrategyConfig:
    """供说明文档 / 未来 RAG ingest 引用的配置快照。"""

    retrieval_unit: str = RETRIEVAL_UNIT
    retrieval_token_limit: int = RETRIEVAL_TOKEN_LIMIT
    retrieval_chunk_size: int = RETRIEVAL_CHUNK_SIZE
    retrieval_chunk_overlap: int = RETRIEVAL_CHUNK_OVERLAP
    body_chunk_size: int = BODY_CHUNK_SIZE
    body_chunk_overlap: int = BODY_CHUNK_OVERLAP
    drop_missing_abstract: bool = True
    drop_short_abstract: bool = False  # 验证期 0 篇；全量可复核后改
    short_abstract_char_threshold: int = SHORT_ABSTRACT_CHAR_THRESHOLD
    notes: list[str] = field(default_factory=lambda: [
        "主体 ~85% title+abstract ≤512：单 chunk",
        "长尾 ~14% >512：RecursiveCharacterTextSplitter",
        "body 一律 sliding_window，与摘要分开",
        "无 abstract：丢弃并记录 pmcid",
    ])


def build_retrieval_text(row: pd.Series | dict[str, Any]) -> str:
    if isinstance(row, pd.Series):
        row = row.to_dict()
    title = str(row.get("title") or "").strip()
    abstract = str(row.get("abstract") or "").strip()
    if title and abstract:
        return f"{title}\n{abstract}"
    return title or abstract


def _get_splitter(
    chunk_size: int,
    chunk_overlap: int,
    length_function: Callable[[str], int],
):
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=length_function,
    )


def chunk_text(
    text: str,
    *,
    tokenizer,
    token_limit: int,
    chunk_size: int,
    chunk_overlap: int,
    source_field: str,
    pmcid: str = "",
    char_safe: int = RETRIEVAL_CHAR_SAFE,
) -> list[ChunkRecord]:
    """按 token 长度：≤limit 单块，否则滑动窗口。"""
    text = (text or "").strip()
    if not text:
        return []

    need_exact = len(text) > char_safe
    token_len = count_tokens(text, tokenizer) if need_exact else len(text) // 4

    if token_len <= token_limit:
        exact = count_tokens(text, tokenizer)
        return [
            ChunkRecord(
                pmcid=pmcid,
                chunk_index=0,
                chunk_count=1,
                text=text,
                token_len=exact,
                source_field=source_field,
                strategy="single",
            )
        ]

    splitter = _get_splitter(
        chunk_size,
        chunk_overlap,
        lambda t: count_tokens(t, tokenizer),
    )
    parts = splitter.split_text(text)
    records: list[ChunkRecord] = []
    for i, part in enumerate(parts):
        records.append(
            ChunkRecord(
                pmcid=pmcid,
                chunk_index=i,
                chunk_count=len(parts),
                text=part,
                token_len=count_tokens(part, tokenizer),
                source_field=source_field,
                strategy="sliding_window",
            )
        )
    return records


def chunk_retrieval_row(
    row: pd.Series | dict[str, Any],
    tokenizer,
    *,
    config: ChunkStrategyConfig | None = None,
) -> list[ChunkRecord]:
    cfg = config or ChunkStrategyConfig()
    if isinstance(row, pd.Series):
        row = row.to_dict()
    pmcid = str(row.get("pmcid") or "")
    text = build_retrieval_text(row)
    return chunk_text(
        text,
        tokenizer=tokenizer,
        token_limit=cfg.retrieval_token_limit,
        chunk_size=cfg.retrieval_chunk_size,
        chunk_overlap=cfg.retrieval_chunk_overlap,
        source_field="retrieval",
        pmcid=pmcid,
    )


def chunk_body_row(
    row: pd.Series | dict[str, Any],
    tokenizer,
    *,
    config: ChunkStrategyConfig | None = None,
) -> list[ChunkRecord]:
    cfg = config or ChunkStrategyConfig()
    if isinstance(row, pd.Series):
        row = row.to_dict()
    pmcid = str(row.get("pmcid") or "")
    return chunk_body_text(
        str(row.get("body") or ""),
        tokenizer,
        pmcid=pmcid,
        config=cfg,
    )
def chunk_body_text(
    body: str,
    tokenizer,
    *,
    pmcid: str = "",
    config: ChunkStrategyConfig | None = None,
) -> list[ChunkRecord]:
    """正文一律 sliding window（不判单块）。"""
    cfg = config or ChunkStrategyConfig()
    body = (body or "").strip()
    if not body:
        return []
    splitter = _get_splitter(
        cfg.body_chunk_size,
        cfg.body_chunk_overlap,
        lambda t: count_tokens(t, tokenizer),
    )
    parts = splitter.split_text(body)
    return [
        ChunkRecord(
            pmcid=pmcid,
            chunk_index=i,
            chunk_count=len(parts),
            text=part,
            token_len=count_tokens(part, tokenizer),
            source_field="body",
            strategy="sliding_window",
        )
        for i, part in enumerate(parts)
    ]


def summarize_retrieval_chunks(
    df: pd.DataFrame,
    tokenizer,
    *,
    config: ChunkStrategyConfig | None = None,
) -> pd.DataFrame:
    """对 df 每行 retrieval 切块，汇总单块/多块篇数。"""
    cfg = config or ChunkStrategyConfig()
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        chunks = chunk_retrieval_row(row, tokenizer, config=cfg)
        if not chunks:
            continue
        strat = chunks[0].strategy if len(chunks) == 1 else "sliding_window"
        rows.append(
            {
                "pmcid": row.get("pmcid"),
                "retrieval_token_len": chunks[0].token_len
                if len(chunks) == 1
                else sum(c.token_len for c in chunks),
                "n_chunks": len(chunks),
                "strategy": strat,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    summary = pd.DataFrame(
        [
            {
                "pmcid": "__summary__",
                "retrieval_token_len": None,
                "n_chunks": int(out["n_chunks"].sum()),
                "strategy": f"single={int((out['n_chunks']==1).sum())}, "
                f"multi={int((out['n_chunks']>1).sum())}",
            }
        ]
    )
    return pd.concat([out, summary], ignore_index=True)


def config_as_dict(config: ChunkStrategyConfig | None = None) -> dict[str, Any]:
    cfg = config or ChunkStrategyConfig()
    return {
        "retrieval_unit": cfg.retrieval_unit,
        "retrieval_token_limit": cfg.retrieval_token_limit,
        "retrieval_chunk_size": cfg.retrieval_chunk_size,
        "retrieval_chunk_overlap": cfg.retrieval_chunk_overlap,
        "body_chunk_size": cfg.body_chunk_size,
        "body_chunk_overlap": cfg.body_chunk_overlap,
        "drop_missing_abstract": cfg.drop_missing_abstract,
        "drop_short_abstract": cfg.drop_short_abstract,
        "short_abstract_char_threshold": cfg.short_abstract_char_threshold,
        "notes": cfg.notes,
    }


def print_strategy_banner(config: ChunkStrategyConfig | None = None) -> None:
    """notebook / ingest 脚本入口打印推荐配置。"""
    cfg = config or ChunkStrategyConfig()
    print("=== 阶段 6：定稿分割策略（供未来 RAG ingest） ===")
    for k, v in config_as_dict(cfg).items():
        if k == "notes":
            print("notes:")
            for n in v:
                print(f"  - {n}")
        else:
            print(f"  {k}: {v}")


__all__ = [
    "BODY_CHUNK_OVERLAP",
    "BODY_CHUNK_SIZE",
    "ChunkRecord",
    "ChunkStrategyConfig",
    "RETRIEVAL_CHUNK_OVERLAP",
    "RETRIEVAL_CHUNK_SIZE",
    "RETRIEVAL_TOKEN_LIMIT",
    "RETRIEVAL_UNIT",
    "build_retrieval_text",
    "chunk_body_text",
    "chunk_retrieval_row",
    "chunk_text",
    "config_as_dict",
    "print_strategy_banner",
    "summarize_retrieval_chunks",
]
