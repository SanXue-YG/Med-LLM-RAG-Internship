# 03 文档解析与分割 — src 模块
from .chunker import DocumentChunker, load_chunk_config, get_default_paths

__all__ = ["DocumentChunker", "load_chunk_config", "get_default_paths"]
