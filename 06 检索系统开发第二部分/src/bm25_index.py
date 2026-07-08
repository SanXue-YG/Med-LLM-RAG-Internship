"""BM25 关键词检索：分词、建索引、top_k 查询。"""

from __future__ import annotations

import json
import pickle
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

try:
    from .config import Mode, resolve_chunks_path
except ImportError:
    from config import Mode, resolve_chunks_path  # type: ignore[no-redef]

# 与 05 query_enhancer 关键词路一致的轻量英文停用词
_STOPWORDS = frozenset(
    "a an the and or of in on for to with is are was were be been being "
    "what how why when which who".split()
)

_TOKEN_RE = re.compile(r"\b[a-z0-9]+\b", re.IGNORECASE)

CHUNK_FIELDS = (
    "chunk_id",
    "text",
    "doc_id",
    "source_title",
    "chunk_index",
    "total_chunks",
    "token_count",
    "strategy",
)


def tokenize(text: str) -> list[str]:
    """英文分词：小写、去停用词，保留含数字的医学术语 token。"""
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS]


class BM25Index:
    """基于 rank-bm25 的 chunk 级关键词索引。"""

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._chunks: list[dict[str, Any]] = []
        self._corpus_tokens: list[list[str]] = []
        self._source_path: Path | None = None

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def source_path(self) -> Path | None:
        return self._source_path

    def build_from_jsonl(
        self,
        jsonl_path: str | Path,
        *,
        limit: int | None = None,
    ) -> int:
        """从 chunks JSONL 构建 BM25 索引，返回入库条数。"""
        path = Path(jsonl_path)
        if not path.is_file():
            raise FileNotFoundError(f"chunks JSONL not found: {path}")

        chunks: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if limit is not None and i >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                chunk = {k: row[k] for k in CHUNK_FIELDS if k in row}
                if "chunk_id" not in chunk or "text" not in chunk:
                    continue
                chunks.append(chunk)

        if not chunks:
            raise ValueError(f"no valid chunks loaded from {path}")

        corpus_tokens = [tokenize(c["text"]) for c in chunks]
        # rank_bm25 要求至少有一个非空文档；空 token 文档用占位避免异常
        corpus_tokens = [t if t else ["_empty_"] for t in corpus_tokens]

        self._chunks = chunks
        self._corpus_tokens = corpus_tokens
        self._bm25 = BM25Okapi(corpus_tokens)
        self._source_path = path.resolve()
        return len(chunks)

    def build(self, mode: Mode = "sample", *, limit: int | None = None) -> int:
        """按 config 默认路径构建索引。"""
        return self.build_from_jsonl(resolve_chunks_path(mode), limit=limit)

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """BM25 检索，返回统一候选格式（含 source/score/rank/chunk_id）。"""
        if self._bm25 is None:
            raise RuntimeError("BM25 index not built; call build() or build_from_jsonl() first")
        if top_k <= 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

        results: list[dict[str, Any]] = []
        for rank_idx, (doc_idx, score) in enumerate(ranked[:top_k], start=1):
            if score <= 0:
                continue
            chunk = self._chunks[doc_idx]
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "doc_id": chunk.get("doc_id"),
                    "source_title": chunk.get("source_title"),
                    "text": chunk.get("text"),
                    "chunk_index": chunk.get("chunk_index"),
                    "total_chunks": chunk.get("total_chunks"),
                    "token_count": chunk.get("token_count"),
                    "strategy": chunk.get("strategy"),
                    "source": "bm25",
                    "score": float(score),
                    "rank": rank_idx,
                }
            )
        return results

    def save(self, directory: str | Path) -> Path:
        """将内存索引落盘（供全量离线复用）。"""
        if self._bm25 is None:
            raise RuntimeError("BM25 index not built; nothing to save")

        out_dir = Path(directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        payload_path = out_dir / "bm25_index.pkl"
        manifest_path = out_dir / "manifest.json"

        source = self._source_path or Path("unknown")
        manifest = {
            "format": "bm25_index_v1",
            "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chunk_count": len(self._chunks),
            "source_jsonl": str(source),
            "source_exists": source.is_file(),
            "source_size_bytes": source.stat().st_size if source.is_file() else None,
            "source_mtime": source.stat().st_mtime if source.is_file() else None,
            "payload_file": payload_path.name,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        with open(payload_path, "wb") as f:
            pickle.dump(
                {
                    "chunks": self._chunks,
                    "corpus_tokens": self._corpus_tokens,
                    "bm25": self._bm25,
                    "source_path": str(source),
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        return out_dir

    @classmethod
    def load(cls, directory: str | Path, *, validate_source: bool = True) -> BM25Index:
        """从离线目录加载索引；可选校验源 JSONL 未变更。"""
        in_dir = Path(directory)
        manifest_path = in_dir / "manifest.json"
        payload_path = in_dir / "bm25_index.pkl"
        if not manifest_path.is_file() or not payload_path.is_file():
            raise FileNotFoundError(f"BM25 cache incomplete under {in_dir}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = Path(str(manifest.get("source_jsonl", "")))
        if validate_source and source.is_file():
            recorded_size = manifest.get("source_size_bytes")
            recorded_mtime = manifest.get("source_mtime")
            if recorded_size is not None and source.stat().st_size != recorded_size:
                raise ValueError(
                    f"source JSONL size changed since cache build: {source} "
                    f"(cached={recorded_size}, current={source.stat().st_size})"
                )
            if recorded_mtime is not None and source.stat().st_mtime != recorded_mtime:
                raise ValueError(f"source JSONL mtime changed since cache build: {source}")

        with open(payload_path, "rb") as f:
            payload = pickle.load(f)

        index = cls()
        index._chunks = payload["chunks"]
        index._corpus_tokens = payload["corpus_tokens"]
        index._bm25 = payload["bm25"]
        index._source_path = Path(payload.get("source_path") or source)
        if manifest.get("chunk_count") != len(index._chunks):
            raise ValueError(
                f"manifest chunk_count={manifest.get('chunk_count')} "
                f"!= loaded {len(index._chunks)}"
            )
        return index

    @classmethod
    def try_load(cls, directory: str | Path, *, validate_source: bool = True) -> BM25Index | None:
        try:
            return cls.load(directory, validate_source=validate_source)
        except (FileNotFoundError, ValueError):
            return None
