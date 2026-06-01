# 04 向量化与索引构建 — src 模块
try:
    from .embedder import DocumentEmbedder, BGE_QUERY_INSTRUCTION
    from .index_builder import ChromaIndexBuilder, METADATA_FIELDS
except ImportError:
    from embedder import DocumentEmbedder, BGE_QUERY_INSTRUCTION
    from index_builder import ChromaIndexBuilder, METADATA_FIELDS

__all__ = [
    "DocumentEmbedder",
    "BGE_QUERY_INSTRUCTION",
    "ChromaIndexBuilder",
    "METADATA_FIELDS",
]
