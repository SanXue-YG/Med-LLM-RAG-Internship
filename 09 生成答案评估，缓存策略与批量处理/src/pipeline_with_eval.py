"""Stage 09 glue pipeline: generation + cache + evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from answer_evaluator import AnswerEvaluator
from generation_cache import GenerationCache
from model_adapter import GenerationRequest, ModelAdapter, PipelineModelAdapter


@dataclass
class PipelineWithEval:
    model_adapter: ModelAdapter
    evaluator: AnswerEvaluator
    cache: GenerationCache
    provider: str = "unknown"
    default_model_name: str = ""

    @classmethod
    def from_pipeline(
        cls,
        pipeline: Any,
        *,
        evaluator: AnswerEvaluator | None = None,
        cache: GenerationCache | None = None,
        provider: str = "stage08_pipeline",
        model_name: str = "",
    ) -> "PipelineWithEval":
        adapter = PipelineModelAdapter(pipeline, provider=provider, model_name=model_name)
        return cls(
            model_adapter=adapter,
            evaluator=evaluator or AnswerEvaluator(),
            cache=cache or GenerationCache(),
            provider=provider,
            default_model_name=model_name,
        )

    def run_with_cache_and_eval(
        self,
        query: str,
        *,
        ground_truth_entry: dict[str, Any],
        use_cache: bool = True,
        force_refresh: bool = False,
        context_text: str = "",
        model_name: str = "",
        temperature: float = 0.2,
        extensions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        active_model = model_name or self.default_model_name or "unknown_model"
        cache_key = self.cache.make_key(query, context_text, active_model, temperature)
        cache_hit = False

        generation_payload: dict[str, Any]
        if use_cache and not force_refresh:
            cached = self.cache.get(cache_key)
            if cached is not None:
                generation_payload = dict(cached)
                cache_hit = True
            else:
                generation_payload = self._run_generation(query, context_text, active_model, temperature)
                self.cache.set(cache_key, generation_payload, temperature=temperature)
        else:
            generation_payload = self._run_generation(query, context_text, active_model, temperature)
            if use_cache:
                self.cache.set(cache_key, generation_payload, temperature=temperature)

        answer_text = str(generation_payload.get("answer", "") or "")
        sources = generation_payload.get("sources", [])
        reference = str(ground_truth_entry.get("reference_answer", "") or "")
        gt_key_phrases = ground_truth_entry.get("key_phrases", []) or []

        evaluation = self.evaluator.evaluate(
            generated=answer_text,
            reference=reference,
            gt_key_phrases=list(gt_key_phrases),
            sources=sources if isinstance(sources, list) else [],
            context=context_text,
        ).to_dict()

        return {
            "query": query,
            "generation": generation_payload,
            "evaluation": evaluation,
            "cache": {
                "hit": cache_hit,
                "key": cache_key,
                "stats": self.cache.stats(),
                "use_cache": use_cache,
                "force_refresh": force_refresh,
            },
            "extensions": extensions or {},
        }

    def _run_generation(
        self, query: str, context_text: str, model_name: str, temperature: float
    ) -> dict[str, Any]:
        req = GenerationRequest(
            query=query,
            context_text=context_text,
            model_name=model_name,
            temperature=temperature,
        )
        response = self.model_adapter.generate(req)
        raw = response.raw if isinstance(response.raw, dict) else {}
        payload = dict(raw)
        payload.setdefault("answer", response.answer)
        payload.setdefault("sources", response.sources)
        payload.setdefault("model_name", response.model_name or model_name)
        payload.setdefault("provider", response.provider or self.provider)
        return payload

