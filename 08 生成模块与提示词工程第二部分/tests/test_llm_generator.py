import json
import sys
from pathlib import Path

import httpx
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from llm_generator import LLMGenerator  # noqa: E402


def _mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "deepseek-r1:7b"}]})
        if request.url.path == "/api/chat":
            payload = json.loads(request.content)
            user = payload["messages"][-1]["content"]
            if "JSON" in user or "json" in user.lower():
                content = '{"answer": "ok", "evidence_points": []}'
            else:
                content = "Metformin may reduce cardiovascular risk."
            return httpx.Response(
                200,
                json={"message": {"role": "assistant", "content": content}},
            )
        return httpx.Response(404, json={"error": "not found"})

    return httpx.MockTransport(handler)


@pytest.fixture
def generator() -> LLMGenerator:
    client = httpx.Client(transport=_mock_transport(), base_url="http://test")
    gen = LLMGenerator("deepseek-r1:7b", "http://test", timeout=10.0, client=client)
    yield gen
    gen.close()


def test_health_check_and_ping(generator: LLMGenerator):
    assert generator.health_check() is True
    assert generator.ping() is True


def test_generate_with_system_prompt(generator: LLMGenerator):
    text = generator.generate(
        "What is metformin?",
        system_prompt="You are a medical assistant.",
        temperature=0.2,
        max_tokens=128,
    )
    assert "Metformin" in text


def test_generate_json_parses_dict(generator: LLMGenerator):
    obj = generator.generate_json('Summarize evidence as JSON.')
    assert obj == {"answer": "ok", "evidence_points": []}


def test_generate_batch_sequential(generator: LLMGenerator):
    results = generator.generate_batch(
        [
            {"prompt": "Q1", "max_tokens": 50},
            {"prompt": "Q2", "system_prompt": "Be brief.", "max_tokens": 50},
        ]
    )
    assert len(results) == 2
    assert all(isinstance(r, str) and r for r in results)
