try:
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
except ImportError:
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

__all__ = [
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
