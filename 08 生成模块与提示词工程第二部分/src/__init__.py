"""08 生成模块与提示词工程第二部分。"""

from bootstrap import OLLAMA_BASE_URL, OLLAMA_MODEL, bootstrap_paths, project_root
from llm_generator import LLMGenerator

__all__ = [
    "LLMGenerator",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "bootstrap_paths",
    "project_root",
]
