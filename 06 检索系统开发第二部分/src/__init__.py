try:
    from .bm25_index import BM25Index, tokenize
    from .config import (
        CHROMA_FULL_DIR,
        CHUNKS_SAMPLE,
        COLLECTION_FULL,
        COLLECTION_SAMPLE,
        DEFAULT_FUSION_STRATEGY,
        EMBED_MODEL,
        RERANK_MODEL,
        resolve_chroma,
        resolve_chunks_path,
        resolve_slim_path,
    )
    from .fusion import fuse
    from .multipath_retriever import MultiPathRetriever, chroma_results_to_hits
    from .reranker import Reranker, DEFAULT_CRITERIA_WEIGHTS
    from .rerank_features import SlimMetadataLookup
except ImportError:
    from bm25_index import BM25Index, tokenize  # type: ignore[no-redef]
    from config import (  # type: ignore[no-redef]
        CHROMA_FULL_DIR,
        CHUNKS_SAMPLE,
        COLLECTION_FULL,
        COLLECTION_SAMPLE,
        DEFAULT_FUSION_STRATEGY,
        EMBED_MODEL,
        RERANK_MODEL,
        resolve_chroma,
        resolve_chunks_path,
        resolve_slim_path,
    )
    from fusion import fuse  # type: ignore[no-redef]
    from multipath_retriever import MultiPathRetriever, chroma_results_to_hits  # type: ignore[no-redef]
    from reranker import Reranker, DEFAULT_CRITERIA_WEIGHTS  # type: ignore[no-redef]
    from rerank_features import SlimMetadataLookup  # type: ignore[no-redef]

__all__ = [
    "BM25Index",
    "DEFAULT_CRITERIA_WEIGHTS",
    "MultiPathRetriever",
    "Reranker",
    "SlimMetadataLookup",
    "chroma_results_to_hits",
    "fuse",
    "tokenize",
    "CHROMA_FULL_DIR",
    "CHUNKS_SAMPLE",
    "COLLECTION_FULL",
    "COLLECTION_SAMPLE",
    "DEFAULT_FUSION_STRATEGY",
    "EMBED_MODEL",
    "RERANK_MODEL",
    "resolve_chroma",
    "resolve_chunks_path",
    "resolve_slim_path",
]
