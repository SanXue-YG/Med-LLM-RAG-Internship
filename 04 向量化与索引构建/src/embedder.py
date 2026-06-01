"""
04 向量化与索引构建 — 嵌入模型封装（BGE）

实现要点（见 笔记/04笔记.md Q10）：
- 文档端 encode_documents()：不加指令前缀（建库用）
- 查询端 encode_queries()：自动加 BGE 指令前缀（检索用）
- 余弦相似度：嵌入向量做 L2 归一化（normalize_embeddings=True）
- 自动选择 device：有 CUDA 用 GPU，否则 CPU
"""

from __future__ import annotations

from typing import Sequence

# BGE 英文检索官方推荐的查询指令前缀
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class DocumentEmbedder:
    """BGE 嵌入模型封装，区分文档端与查询端。"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        device: str | None = None,
        batch_size: int = 64,
        query_instruction: str = BGE_QUERY_INSTRUCTION,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.query_instruction = query_instruction

        # 自动选择设备
        if device is None:
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        self.device = device

        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    @property
    def dimension(self) -> int:
        """嵌入向量维度（bge-small = 384）。"""
        return self.model.get_sentence_embedding_dimension()

    def encode_documents(self, texts: Sequence[str], show_progress: bool = False):
        """文档端编码：不加指令前缀。用于建库。

        返回 list[list[float]]，已 L2 归一化（配合余弦相似度）。
        """
        embeddings = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def encode_queries(self, texts: Sequence[str], show_progress: bool = False):
        """查询端编码：自动加 BGE 指令前缀。用于检索。

        返回 list[list[float]]，已 L2 归一化。
        """
        prefixed = [self.query_instruction + t for t in texts]
        embeddings = self.model.encode(
            prefixed,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    def device_info(self) -> dict:
        """返回当前设备信息，便于 notebook 记录背景。"""
        info = {"model_name": self.model_name, "device": self.device}
        try:
            import torch

            info["torch_version"] = torch.__version__
            info["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                info["gpu_name"] = torch.cuda.get_device_name(0)
        except ImportError:
            info["torch_version"] = None
        return info
