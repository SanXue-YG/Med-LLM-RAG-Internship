"""Model adapter interfaces for future multi-LLM integration.

Current stage keeps implementation lightweight:
- BatchRunner remains model-agnostic by accepting a callable task_fn.
- This module reserves typed interfaces for later stage4/stage5 integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class GenerationRequest:
    query: str
    context_text: str = ""
    model_name: str = ""
    temperature: float = 0.2
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResponse:
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    model_name: str = ""
    provider: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class ModelAdapter(Protocol):
    """Provider/model neutral generation interface."""

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate answer from a normalized request."""


class PipelineModelAdapter:
    """Adapter wrapper for existing pipeline objects.

    Expected wrapped pipeline API:
    - pipeline.run(query: str) -> dict with at least `answer`, optional `sources`.
    """

    def __init__(self, pipeline: Any, *, provider: str = "local_pipeline", model_name: str = "") -> None:
        self.pipeline = pipeline
        self.provider = provider
        self.model_name = model_name

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        result = self.pipeline.run(request.query)
        return GenerationResponse(
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            model_name=request.model_name or self.model_name,
            provider=self.provider,
            raw=result,
        )

