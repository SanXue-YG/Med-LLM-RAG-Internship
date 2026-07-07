"""Answer evaluator for stage 09.

Important: hallucination score is a risk signal from heuristics, not a final truth verdict.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from rouge_score import rouge_scorer

from patterns import (
    DOSAGE_PATTERN,
    HALLUCINATION_SIGNAL_PATTERNS,
    MECHANISM_KEYWORDS,
    PERCENT_PATTERN,
    SAFETY_KEYWORDS,
    TIME_RANGE_PATTERN,
    TREATMENT_KEYWORDS,
)


@dataclass
class EvaluationResult:
    rouge: dict[str, float]
    key_info_recall: float
    key_info_matched: list[str]
    key_info_missing: list[str]
    hallucination_risk: float
    hallucination_signals: list[str]
    readability: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AnswerEvaluator:
    def __init__(self, *, use_stemmer: bool = True) -> None:
        self._rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=use_stemmer)

    def score_rouge(self, generated: str, reference: str) -> dict[str, float]:
        if not generated.strip() or not reference.strip():
            return {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}
        scores = self._rouge.score(reference, generated)
        return {
            "rouge1": round(scores["rouge1"].fmeasure, 4),
            "rouge2": round(scores["rouge2"].fmeasure, 4),
            "rougeL": round(scores["rougeL"].fmeasure, 4),
        }

    def extract_key_info(self, text: str) -> list[str]:
        lowered = text.lower()
        found: set[str] = set()

        for match in PERCENT_PATTERN.findall(text):
            found.add(match.lower().strip())
        for match in DOSAGE_PATTERN.findall(text):
            found.add(match.lower().strip())
        for match in TIME_RANGE_PATTERN.findall(text):
            found.add(match.lower().strip())

        for kw in SAFETY_KEYWORDS + TREATMENT_KEYWORDS + MECHANISM_KEYWORDS:
            if kw in lowered:
                found.add(kw)
        return sorted(found)

    def key_info_recall(self, generated: str, gt_phrases: list[str]) -> tuple[float, list[str], list[str]]:
        normalized_gt = [self._normalize_space(p) for p in gt_phrases if p and p.strip()]
        if not normalized_gt:
            return 0.0, [], []

        generated_low = self._normalize_space(generated)
        matched = [p for p in normalized_gt if p in generated_low]
        missing = [p for p in normalized_gt if p not in generated_low]
        recall = len(matched) / len(normalized_gt) if normalized_gt else 0.0
        return round(recall, 4), matched, missing

    def detect_hallucination_signals(self, text: str) -> tuple[float, list[str]]:
        signals: list[str] = []
        risk = 0.0
        for label, pattern, weight in HALLUCINATION_SIGNAL_PATTERNS:
            if pattern.search(text):
                signals.append(label)
                risk += weight
        return round(min(1.0, risk), 4), signals

    def readability_metrics(self, text: str) -> dict[str, float]:
        sentence_parts = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        words = re.findall(r"\b\w+\b", text)

        num_sentences = len(sentence_parts)
        num_words = len(words)
        avg_sentence_len = (num_words / num_sentences) if num_sentences else 0.0
        avg_word_len = (sum(len(w) for w in words) / num_words) if num_words else 0.0
        return {
            "num_sentences": float(num_sentences),
            "num_words": float(num_words),
            "avg_sentence_len_words": round(avg_sentence_len, 4),
            "avg_word_len_chars": round(avg_word_len, 4),
        }

    def link_signals_with_sources(
        self, risk: float, signals: list[str], sources: list[dict[str, Any]] | None = None
    ) -> tuple[float, list[str]]:
        """Placeholder for future source-aware risk adjustment."""
        _ = sources
        return risk, signals

    def evaluate(
        self,
        generated: str,
        reference: str,
        *,
        gt_key_phrases: list[str] | None = None,
        context: str | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> EvaluationResult:
        _ = context
        rouge = self.score_rouge(generated, reference)
        recall, matched, missing = self.key_info_recall(generated, gt_key_phrases or [])
        risk, signals = self.detect_hallucination_signals(generated)
        risk, signals = self.link_signals_with_sources(risk, signals, sources=sources)
        readability = self.readability_metrics(generated)
        return EvaluationResult(
            rouge=rouge,
            key_info_recall=recall,
            key_info_matched=matched,
            key_info_missing=missing,
            hallucination_risk=risk,
            hallucination_signals=signals,
            readability=readability,
        )

    @staticmethod
    def _normalize_space(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()

