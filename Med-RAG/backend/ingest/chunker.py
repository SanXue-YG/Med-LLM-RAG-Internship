"""
03 文档解析与分割 — 核心分割模块

实现第二阶段确定的分割策略：
- 检索单元：title + abstract
- 短文本（≤512 tokens）：不分割，整块
- 长文本（>512 tokens）：RecursiveCharacterTextSplitter(chunk_size=400, overlap=80)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


class DocumentChunker:
    """文档分割器：实现 title+abstract 的智能分割策略"""

    def __init__(
        self,
        token_limit: int = 512,
        chunk_size: int = 400,
        chunk_overlap: int = 80,
        tokenizer_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.token_limit = token_limit
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer_name = tokenizer_name

        self._tokenizer = None
        self._splitter = None

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            model = SentenceTransformer(self.tokenizer_name)
            self._tokenizer = model.tokenizer
        return self._tokenizer

    @property
    def splitter(self) -> RecursiveCharacterTextSplitter:
        if self._splitter is None:
            self._splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=self._count_tokens,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
        return self._splitter

    def _count_tokens(self, text: str) -> int:
        """使用 tokenizer 计算 token 数量"""
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def chunk_document(self, doc: dict[str, Any]) -> list[dict[str, Any]]:
        """
        对单篇文档进行分割

        Args:
            doc: 包含 pmcid, title, abstract 的字典

        Returns:
            分割后的 chunk 列表，每个 chunk 包含任务书要求的字段
        """
        pmcid = doc.get("pmcid", "")
        title = doc.get("title", "")
        abstract = doc.get("abstract", "")

        full_text = f"{title}\n\n{abstract}".strip()
        token_count = self._count_tokens(full_text)

        chunks = []

        if token_count <= self.token_limit:
            chunk_data = {
                "chunk_id": pmcid,
                "text": full_text,
                "doc_id": pmcid,
                "chunk_index": 0,
                "total_chunks": 1,
                "source_title": title,
                "token_count": token_count,
                "strategy": "single",
            }
            chunks.append(chunk_data)
        else:
            texts = self.splitter.split_text(full_text)
            total_chunks = len(texts)
            for i, text in enumerate(texts):
                chunk_id = f"{pmcid}_chunk{i}"
                chunk_data = {
                    "chunk_id": chunk_id,
                    "text": text,
                    "doc_id": pmcid,
                    "chunk_index": i,
                    "total_chunks": total_chunks,
                    "source_title": title,
                    "token_count": self._count_tokens(text),
                    "strategy": "sliding_window",
                }
                chunks.append(chunk_data)

        return chunks

    def process_jsonl_stream(
        self,
        input_path: str | Path,
        output_path: str | Path,
        limit: int | None = None,
        resume: bool = True,
    ) -> dict[str, Any]:
        """
        流式处理 JSONL 文件，支持断点续传

        Args:
            input_path: 输入 JSONL 路径（oa_comm_slim.jsonl）
            output_path: 输出 JSONL 路径
            limit: 限制处理数量（调试用）
            resume: 是否启用断点续传

        Returns:
            处理统计信息
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        progress_file = output_path.with_suffix(".progress.json")

        processed_docs = 0
        total_chunks = 0
        single_count = 0
        multi_count = 0

        start_line = 0
        if resume and progress_file.exists():
            with open(progress_file, "r", encoding="utf-8") as f:
                progress = json.load(f)
                start_line = progress.get("processed_lines", 0)
                processed_docs = progress.get("processed_docs", 0)
                total_chunks = progress.get("total_chunks", 0)
                single_count = progress.get("single_count", 0)
                multi_count = progress.get("multi_count", 0)
                print(f"[续传] 从第 {start_line} 行继续，已处理 {processed_docs} 篇")

        # 计算总行数（用于进度条）
        if limit:
            # 调试模式：快速统计
            total_lines = sum(1 for _ in open(input_path, "r", encoding="utf-8"))
            total_lines = min(total_lines, limit + start_line)
        else:
            # 全量模式：使用已知行数避免长时间扫描
            # oa_comm_slim.jsonl 已知约 4,557,627 行
            total_lines = 4_557_627
            print(f"[全量模式] 使用预设行数: {total_lines:,}（跳过行数统计）")

        mode = "a" if resume and start_line > 0 else "w"

        with (
            open(input_path, "r", encoding="utf-8") as fin,
            open(output_path, mode, encoding="utf-8") as fout,
        ):
            for line_no, line in enumerate(
                tqdm(fin, total=total_lines, desc="分割文档", initial=start_line)
            ):
                if line_no < start_line:
                    continue

                if limit and (line_no - start_line) >= limit:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    doc = json.loads(line)
                    chunks = self.chunk_document(doc)

                    for chunk in chunks:
                        fout.write(json.dumps(chunk, ensure_ascii=False) + "\n")

                    processed_docs += 1
                    total_chunks += len(chunks)
                    if len(chunks) == 1:
                        single_count += 1
                    else:
                        multi_count += 1

                    if processed_docs % 10000 == 0:
                        self._save_progress(
                            progress_file,
                            line_no + 1,
                            processed_docs,
                            total_chunks,
                            single_count,
                            multi_count,
                        )

                except json.JSONDecodeError as e:
                    print(f"[警告] 第 {line_no} 行 JSON 解析失败: {e}")
                    continue

        self._save_progress(
            progress_file,
            total_lines,
            processed_docs,
            total_chunks,
            single_count,
            multi_count,
        )

        stats = {
            "processed_docs": processed_docs,
            "total_chunks": total_chunks,
            "single_count": single_count,
            "multi_count": multi_count,
            "single_ratio": single_count / processed_docs if processed_docs > 0 else 0,
            "multi_ratio": multi_count / processed_docs if processed_docs > 0 else 0,
            "avg_chunks_per_doc": total_chunks / processed_docs if processed_docs > 0 else 0,
        }
        return stats

    def _save_progress(
        self,
        progress_file: Path,
        processed_lines: int,
        processed_docs: int,
        total_chunks: int,
        single_count: int,
        multi_count: int,
    ):
        """保存处理进度"""
        progress = {
            "processed_lines": processed_lines,
            "processed_docs": processed_docs,
            "total_chunks": total_chunks,
            "single_count": single_count,
            "multi_count": multi_count,
        }
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2)


def load_chunk_config(config_path: str | Path) -> dict[str, Any]:
    """加载第二阶段的分割策略配置"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_default_paths() -> dict[str, Path]:
    """获取默认路径配置"""
    if os.name == "nt":
        data_root = Path("E:/med-llm-rag-datasets")
    else:
        data_root = Path("/Volumes/Lexar/med-llm-rag-datasets")

    return {
        "data_root": data_root,
        "input_jsonl": data_root / "processed" / "oa_comm_slim.jsonl",
        "output_jsonl": data_root / "processed" / "oa_comm_chunks.jsonl",
        "chunk_config": Path(__file__).parent.parent.parent
        / "02 数据处理"
        / "outputs"
        / "tables"
        / "chunk_strategy_config.json",
    }
