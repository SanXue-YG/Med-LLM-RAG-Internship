"""
04 向量化与索引构建 — ChromaDB 索引构建与查询

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

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where_filter: dict | None = None,
    ) -> dict[str, Any]:
        """语义检索：查询端自动加 BGE 指令前缀。"""
        query_emb = self.embedder.encode_queries([query_text])
        return self.collection.query(
            query_embeddings=query_emb,
            n_results=n_results,
            where=where_filter,
        )

    # ---------- 统计 ----------

    def get_stats(self, chunk_token_stats: dict | None = None) -> dict[str, Any]:
        """生成索引统计信息（对齐任务书 §2 stats 结构）。"""
        return {
            "collection_name": self.collection_name,
            "total_chunks": self.collection.count(),
            "embedding_model": self.embedder.model_name,
            "embedding_dimension": self.embedder.dimension,
            "index_built_at": datetime.now().isoformat(),
            "distance": "cosine",
            "chunk_size_stats": chunk_token_stats or {},
            "metadata_fields": METADATA_FIELDS,
        }
