"""Ollama HTTP 生成器（阶段 08 LLMGenerator）。"""

from __future__ import annotations

from typing import Any

import httpx

from bootstrap import OLLAMA_BASE_URL, OLLAMA_MODEL
from json_utils import extract_json
_JSON_SUFFIX = (
    "\n\nRespond with a single valid JSON object only. "
    "No markdown fences or extra commentary."
)


def _strip_thinking_markers(text: str) -> str:
    """移除 deepseek-r1 在 ``response`` 中嵌入的 thinking 标记（对齐 01 阶段）。"""
    if not text:
        return ""
    if "</think>" in text:
        return text.split("</think>", 1)[1].strip()
    if "<think>" in text:
        return ""
    return text.strip()


class LLMGenerator:
    """通过 Ollama ``/api/chat`` 调用本地 LLM。"""

    def __init__(
        self,
        model_name: str = OLLAMA_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: float = 120.0,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)
            self._owns_client = True
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> LLMGenerator:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def health_check(self) -> bool:
        """探测 Ollama 服务是否可达。"""
        return self.ping()

    def ping(self) -> bool:
        try:
            resp = self._get_client().get("/api/tags")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        json_mode: bool = False,
        think: bool = False,
    ) -> str:
        """单次生成；``json_mode`` 时在 user 末尾追加 JSON 格式约束。"""
        user_content = prompt + (_JSON_SUFFIX if json_mode else "")
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_content})

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "think": think,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        resp = self._get_client().post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message") or {}
        content = message.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        content = _strip_thinking_markers(content)
        return content

    def generate_json(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        think: bool = False,
    ) -> dict | None:
        """生成并解析 JSON；解析失败返回 ``None``。"""
        raw = self.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
            think=think,
        )
        return extract_json(raw)
    def generate_batch(self, requests: list[dict[str, Any]]) -> list[str]:
        """顺序批量生成；每项为 ``generate()`` 关键字参数字典（须含 ``prompt``）。"""
        outputs: list[str] = []
        for item in requests:
            params = dict(item)
            prompt = params.pop("prompt")
            outputs.append(self.generate(prompt, **params))
        return outputs
