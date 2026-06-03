"""
04 向量化与索引构建 — 嵌入模型封装（BGE）

默认模型：BAAI/bge-small-en-v1.5（384 维）。本阶段全部向量与检索结果均基于此模型；
详见 docs/向量化与索引报告.md §2。

实现要点（见 笔记/04笔记.md Q10）：
- 文档端 encode_documents()：不加指令前缀（建库用）
- 查询端 encode_queries()：自动加 BGE 指令前缀（检索用）
- 余弦相似度：嵌入向量做 L2 归一化
- 自动选择 device：有 CUDA 用 GPU，否则 CPU

注：直接使用 transformers（AutoModel），不依赖 sentence-transformers。
     避免 Windows Jupyter 下 sentence_transformers → pyarrow 导入链导致内核崩溃。
"""

from __future__ import annotations

import os
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
        max_length: int = 512,
    ):
        self.model_name = model_name
        self.batch_size = batch_size
        self.query_instruction = query_instruction
        self.max_length = max_length

        if device is None:
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"
        self.device = device

        self._tokenizer = None
        self._model = None
        self._dimension: int | None = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

        import torch
        from transformers import AutoModel, AutoTokenizer
        from transformers.utils.logging import disable_progress_bar

        disable_progress_bar()

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModel.from_pretrained(self.model_name)
        self._model.to(self.device)
        self._model.eval()
        self._dimension = int(self._model.config.hidden_size)

    @property
    def dimension(self) -> int:
        """嵌入向量维度（bge-small = 384）。"""
        if self._dimension is not None:
            return self._dimension
        from transformers import AutoConfig

        return int(AutoConfig.from_pretrained(self.model_name).hidden_size)

    @staticmethod
    def _mean_pooling(token_embeddings, attention_mask):
        import torch

        mask = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        summed = torch.sum(token_embeddings * mask, dim=1)
        counts = torch.clamp(mask.sum(dim=1), min=1e-9)
        return summed / counts

    def _encode_texts(self, texts: Sequence[str], show_progress: bool = False):
        import torch
        import torch.nn.functional as F

        self._ensure_loaded()
        assert self._tokenizer is not None and self._model is not None

        texts = list(texts)
        if not texts:
            return []

        batches = range(0, len(texts), self.batch_size)
        if show_progress:
            from tqdm import tqdm

            batches = tqdm(batches, desc="embedding", file=None)

        all_embeddings = []
        for start in batches:
            batch_texts = texts[start : start + self.batch_size]
            encoded = self._tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            encoded = {k: v.to(self.device) for k, v in encoded.items()}
            with torch.no_grad():
                outputs = self._model(**encoded)
                pooled = self._mean_pooling(outputs.last_hidden_state, encoded["attention_mask"])
                pooled = F.normalize(pooled, p=2, dim=1)
            all_embeddings.append(pooled.cpu())

        return torch.cat(all_embeddings, dim=0).tolist()

    def encode_documents(self, texts: Sequence[str], show_progress: bool = False):
        """文档端编码：不加指令前缀。用于建库。"""
        return self._encode_texts(texts, show_progress=show_progress)

    def encode_queries(self, texts: Sequence[str], show_progress: bool = False):
        """查询端编码：自动加 BGE 指令前缀。用于检索。"""
        prefixed = [self.query_instruction + t for t in texts]
        return self._encode_texts(prefixed, show_progress=show_progress)

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
