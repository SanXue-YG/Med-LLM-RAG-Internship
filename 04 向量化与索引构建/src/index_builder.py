"""
04 向量化与索引构建 — ChromaDB 索引构建与查询

当前索引与 query() 检索结果均对应嵌入模型 BAAI/bge-small-en-v1.5（384 维），
由传入的 DocumentEmbedder 决定；更换模型须全库重建。详见 docs/向量化与索引报告.md。

实现要点：
- 持久化 collection，余弦相似度（hnsw:space=cosine）
- 唯一 id = chunk_id（即 doc_id + chunk_index，阶段 3 已生成）
- 元数据：doc_id, chunk_index, total_chunks, source_title, token_count, strategy
- 分批入库 + 断点续传（progress.json）
- query() 支持 n_results 与元数据过滤 where_filter
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .embedder import DocumentEmbedder
except ImportError:
    from embedder import DocumentEmbedder

METADATA_FIELDS = [
    "doc_id",
    "chunk_index",
    "total_chunks",
    "source_title",
    "token_count",
    "strategy",
]

HNSW_SEGMENT_TYPE = "urn:chroma:segment/vector/hnsw-local-persisted"


def repair_chroma_hnsw(persist_dir: str | Path, collection_name: str | None = None) -> list[str]:
    """修复「Error loading hnsw index」：删除损坏的 HNSW 段目录或 stale pickle。

    Chroma 在 sqlite 中仍保留 embeddings / documents。
    Chroma 1.5.x 常见问题：HNSW 目录仅剩 index_metadata.pickle、缺少 data_level0.bin，
    删 pickle 后 count/query 可从 sqlite 重建索引。

    同时删除 persist_dir 下不在 sqlite segments 表中的 orphan uuid 目录。
    """
    import shutil
    import sqlite3

    persist_dir = Path(persist_dir)
    db_path = persist_dir / "chroma.sqlite3"
    if not db_path.is_file():
        return []

    removed: list[str] = []
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    if collection_name:
        cur.execute(
            """
            SELECT s.id FROM segments s
            JOIN collections c ON s.collection = c.id
            WHERE c.name = ? AND s.type = ?
            """,
            (collection_name, HNSW_SEGMENT_TYPE),
        )
    else:
        cur.execute("SELECT id FROM segments WHERE type = ?", (HNSW_SEGMENT_TYPE,))

    hnsw_ids = {row[0] for row in cur.fetchall()}

    cur.execute("SELECT id FROM segments")
    valid_ids = {row[0] for row in cur.fetchall()}
    con.close()

    for seg_id in hnsw_ids:
        seg_dir = persist_dir / seg_id
        if seg_dir.is_dir():
            shutil.rmtree(seg_dir)
            removed.append(str(seg_dir))

    # Chroma 1.5.x：HNSW 目录若仅有 index_metadata.pickle、缺少 data_level0.bin 等，
    # count/query 会报 "Error loading hnsw index"；删 pickle 后可从 sqlite 重建。
    _hnsw_bin_markers = ("data_level0.bin", "link_lists.bin", "length.bin")
    for seg_id in hnsw_ids:
        seg_dir = persist_dir / seg_id
        if not seg_dir.is_dir():
            continue
        pickle_path = seg_dir / "index_metadata.pickle"
        has_bin = any((seg_dir / name).is_file() for name in _hnsw_bin_markers)
        if pickle_path.is_file() and not has_bin:
            pickle_path.unlink()
            removed.append(str(pickle_path))

    for item in persist_dir.iterdir():
        if not item.is_dir():
            continue
        if len(item.name) == 36 and item.name not in valid_ids:
            shutil.rmtree(item)
            removed.append(str(item))

    return removed


def count_embeddings_sqlite(persist_dir: str | Path) -> int:
    """从 chroma.sqlite3 读取 embedding 条数，避免大库上 collection.count() 触发 native 崩溃。"""
    import sqlite3

    db_path = Path(persist_dir) / "chroma.sqlite3"
    if not db_path.is_file():
        return 0
    con = sqlite3.connect(db_path)
    try:
        return int(con.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0])
    finally:
        con.close()


class ChromaIndexBuilder:
    """基于 ChromaDB 的向量索引构建器。"""

    def __init__(
        self,
        persist_dir: str | Path,
        collection_name: str,
        embedder: DocumentEmbedder,
    ):
        self.persist_dir = str(persist_dir)
        self.collection_name = collection_name
        self.embedder = embedder

        os.makedirs(self.persist_dir, exist_ok=True)

        import chromadb

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        # 余弦相似度
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ---------- 建库 ----------

    def _progress_path(self) -> Path:
        return Path(self.persist_dir) / f"{self.collection_name}.progress.json"

    def _load_progress(self) -> dict:
        p = self._progress_path()
        if p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"processed_lines": 0}

    def _save_progress(self, processed_lines: int) -> None:
        with open(self._progress_path(), "w", encoding="utf-8") as f:
            json.dump({"processed_lines": processed_lines}, f, indent=2)

    def build_from_jsonl(
        self,
        jsonl_path: str | Path,
        batch_size: int = 256,
        resume: bool = True,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """从 chunks JSONL 分批构建索引，支持断点续传。"""
        jsonl_path = Path(jsonl_path)

        start_line = 0
        if resume:
            start_line = self._load_progress().get("processed_lines", 0)
            if start_line > 0:
                print(f"[续传] 从第 {start_line} 行继续")

        buf_ids: list[str] = []
        buf_texts: list[str] = []
        buf_metas: list[dict] = []
        processed = 0

        def flush():
            nonlocal buf_ids, buf_texts, buf_metas
            if not buf_ids:
                return
            embeddings = self.embedder.encode_documents(buf_texts)
            self.collection.add(
                ids=buf_ids,
                embeddings=embeddings,
                documents=buf_texts,
                metadatas=buf_metas,
            )
            buf_ids, buf_texts, buf_metas = [], [], []

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f):
                if line_no < start_line:
                    continue
                if limit is not None and (line_no - start_line) >= limit:
                    break

                line = line.strip()
                if not line:
                    continue

                rec = json.loads(line)
                buf_ids.append(rec["chunk_id"])
                buf_texts.append(rec["text"])
                buf_metas.append(
                    {k: rec.get(k) for k in METADATA_FIELDS if rec.get(k) is not None}
                )

                if len(buf_ids) >= batch_size:
                    flush()
                    processed = line_no + 1
                    self._save_progress(processed)
                    print(f"  已入库 {self.collection.count():,} 条", end="\r")

            flush()
            processed = line_no + 1
            self._save_progress(processed)

        print()
        return {"total_in_collection": self.collection.count()}

    # ---------- 查询 ----------

    @staticmethod
    def _metadata_matches(meta: dict, where_filter: dict) -> bool:
        """简单等值 where 过滤（与 notebook 验证用法一致）。"""
        for key, expected in where_filter.items():
            if meta.get(key) != expected:
                return False
        return True

    def _query_post_filter(
        self,
        query_emb: list[list[float]],
        n_results: int,
        where_filter: dict,
    ) -> dict[str, Any]:
        """Chroma 1.5.x 全量大库 where= 可能报 Error finding id；先稠密检索再 Python 过滤。"""
        fetch = min(max(n_results * 80, 200), 500)
        raw = self.collection.query(
            query_embeddings=query_emb,
            n_results=fetch,
            include=["metadatas", "documents", "distances"],
        )
        ids_out: list[str] = []
        dist_out: list[float] = []
        meta_out: list[dict] = []
        doc_out: list[str] = []
        for cid, dist, meta, doc in zip(
            raw["ids"][0],
            raw["distances"][0],
            raw["metadatas"][0],
            raw["documents"][0],
        ):
            if not self._metadata_matches(meta, where_filter):
                continue
            ids_out.append(cid)
            dist_out.append(dist)
            meta_out.append(meta)
            doc_out.append(doc)
            if len(ids_out) >= n_results:
                break
        return {
            "ids": [ids_out],
            "distances": [dist_out],
            "metadatas": [meta_out],
            "documents": [doc_out],
        }

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where_filter: dict | None = None,
    ) -> dict[str, Any]:
        """语义检索：查询端自动加 BGE 指令前缀。

        带 where_filter 时先走 Chroma 原生过滤；全量大库若报 Error finding id，
        自动降级为「多取候选 + Python 元数据过滤」（Chroma #7032 已知问题）。
        """
        query_emb = self.embedder.encode_queries([query_text])
        if where_filter is None:
            return self.collection.query(
                query_embeddings=query_emb,
                n_results=n_results,
            )
        try:
            return self.collection.query(
                query_embeddings=query_emb,
                n_results=n_results,
                where=where_filter,
            )
        except Exception as e:
            msg = str(e).lower()
            if "finding id" not in msg and "hnsw" not in msg:
                raise
            print(
                "  [query] Chroma where= 失败，改用 over-fetch + Python 过滤 "
                f"({type(e).__name__})"
            )
            return self._query_post_filter(query_emb, n_results, where_filter)

    # ---------- 统计 ----------

    def get_stats(
        self,
        chunk_token_stats: dict | None = None,
        total_chunks: int | None = None,
    ) -> dict[str, Any]:
        """生成索引统计信息（对齐任务书 §2 stats 结构）。

        total_chunks 可传入 progress/sqlite 条数，避免全量库上重复 count() 崩溃。
        """
        if total_chunks is None:
            total_chunks = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "total_chunks": total_chunks,
            "embedding_model": self.embedder.model_name,
            "embedding_dimension": self.embedder.dimension,
            "index_built_at": datetime.now().isoformat(),
            "distance": "cosine",
            "chunk_size_stats": chunk_token_stats or {},
            "metadata_fields": METADATA_FIELDS,
        }
