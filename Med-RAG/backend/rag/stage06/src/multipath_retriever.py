"""多路检索：向量（Chroma）+ 关键词（BM25）→ 融合。"""

from __future__ import annotations

from typing import Any

try:
    from .bm25_index import BM25Index
    from .config import (
        DEFAULT_FUSION_STRATEGY,
        EMBED_MODEL,
        Mode,
        resolve_bm25_cache_dir,
        resolve_chroma,
        stage04_src,
    )
    from .fusion import FusionStrategy, fuse
except ImportError:
    from bm25_index import BM25Index  # type: ignore[no-redef]
    from config import (  # type: ignore[no-redef]
        DEFAULT_FUSION_STRATEGY,
        EMBED_MODEL,
        Mode,
        resolve_bm25_cache_dir,
        resolve_chroma,
        stage04_src,
    )
    from fusion import FusionStrategy, fuse  # type: ignore[no-redef]


def chroma_results_to_hits(res: dict[str, Any]) -> list[dict[str, Any]]:
    """将 Chroma query 结果转为与 BM25 对齐的候选格式。"""
    ids = res.get("ids", [[]])[0]
    dists = res.get("distances", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    docs = res.get("documents", [[]])[0]

    hits: list[dict[str, Any]] = []
    for rank, (cid, dist, meta, doc) in enumerate(zip(ids, dists, metas, docs), start=1):
        hits.append(
            {
                "chunk_id": cid,
                "doc_id": meta.get("doc_id"),
                "source_title": meta.get("source_title"),
                "text": doc,
                "chunk_index": meta.get("chunk_index"),
                "total_chunks": meta.get("total_chunks"),
                "token_count": meta.get("token_count"),
                "strategy": meta.get("strategy"),
                "source": "vector",
                "score": float(1.0 - dist),
                "distance": float(dist),
                "rank": rank,
            }
        )
    return hits


class MultiPathRetriever:
    """向量 + BM25 双路召回，支持 simple / rrf / weighted 融合。"""

    def __init__(
        self,
        builder: Any,
        bm25_index: BM25Index,
        *,
        mode: Mode = "sample",
    ) -> None:
        self.builder = builder
        self.bm25_index = bm25_index
        self.mode = mode

    @classmethod
    def from_mode(cls, mode: Mode = "sample") -> MultiPathRetriever:
        """按 config 挂载 04 Chroma + 06 BM25（需已 build）。"""
        import sys

        chroma_dir, collection = resolve_chroma(mode)
        s04 = stage04_src()
        if str(s04) not in sys.path:
            sys.path.insert(0, str(s04))
        from embedder import DocumentEmbedder  # noqa: WPS433
        from index_builder import ChromaIndexBuilder  # noqa: WPS433

        embedder = DocumentEmbedder(model_name=EMBED_MODEL)
        builder = ChromaIndexBuilder(str(chroma_dir), collection, embedder)
        cache_dir = resolve_bm25_cache_dir(mode)
        if cache_dir is not None:
            try:
                from .bm25_sharded import ShardedBM25Index
            except ImportError:
                from bm25_sharded import ShardedBM25Index  # type: ignore[no-redef]
            if ShardedBM25Index.is_sharded(cache_dir):
                bm25 = ShardedBM25Index(cache_dir)
            else:
                bm25 = BM25Index.load(cache_dir)
        else:
            bm25 = BM25Index()
            bm25.build(mode=mode)
        return cls(builder, bm25, mode=mode)

    def retrieve_vector(self, query_info: Any, top_k: int = 20) -> list[dict[str, Any]]:
        """向量路：输入 05 EnhancedQuery.vector_query。"""
        where = query_info.chroma_where() if hasattr(query_info, "chroma_where") else None
        res = self.builder.query(query_info.vector_query, n_results=top_k, where_filter=where)
        return chroma_results_to_hits(res)

    def retrieve_keyword(self, query_info: Any, top_k: int = 20) -> list[dict[str, Any]]:
        """关键词路：输入 05 EnhancedQuery.keyword_query。"""
        return self.bm25_index.search(query_info.keyword_query, top_k=top_k)

    def retrieve(
        self,
        query_info: Any,
        top_k_vector: int = 20,
        top_k_keyword: int = 20,
        fusion_strategy: FusionStrategy | str = DEFAULT_FUSION_STRATEGY,
        top_k_fused: int = 10,
        **fusion_kwargs: Any,
    ) -> dict[str, Any]:
        """双路召回 + 融合，返回分路与融合结果。"""
        vector_hits = self.retrieve_vector(query_info, top_k=top_k_vector)
        keyword_hits = self.retrieve_keyword(query_info, top_k=top_k_keyword)
        fused = fuse(
            vector_hits,
            keyword_hits,
            strategy=fusion_strategy,  # type: ignore[arg-type]
            top_k=top_k_fused,
            **fusion_kwargs,
        )
        return {
            "query": getattr(query_info, "original", ""),
            "vector_query": query_info.vector_query,
            "keyword_query": query_info.keyword_query,
            "fusion_strategy": fusion_strategy,
            "vector_hits": vector_hits,
            "keyword_hits": keyword_hits,
            "fused": fused,
        }
