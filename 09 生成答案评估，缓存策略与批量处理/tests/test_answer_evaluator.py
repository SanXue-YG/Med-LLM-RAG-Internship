from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from answer_evaluator import AnswerEvaluator


def test_score_rouge_has_overlap() -> None:
    evaluator = AnswerEvaluator()
    generated = "Metformin shows cardiovascular benefit in type 2 diabetes."
    reference = "Cardiovascular benefit of metformin is reported in type 2 diabetes."
    scores = evaluator.score_rouge(generated, reference)
    assert scores["rouge1"] > 0.3
    assert scores["rougeL"] > 0.2


def test_key_info_recall_matches_subset() -> None:
    evaluator = AnswerEvaluator()
    generated = "Use warfarin with INR monitoring and assess bleeding risk in elderly patients."
    gt = ["warfarin", "INR monitoring", "bleeding risk", "stroke prevention"]
    recall, matched, missing = evaluator.key_info_recall(generated, gt)
    assert recall == 0.75
    assert "warfarin" in matched
    assert "stroke prevention" in missing


def test_detect_hallucination_signals() -> None:
    evaluator = AnswerEvaluator()
    text = "This has been proven and is 100% effective and completely safe."
    risk, signals = evaluator.detect_hallucination_signals(text)
    assert risk > 0.0
    assert "has_been_proven" in signals
    assert "absolute_100_percent" in signals


def test_evaluate_returns_all_sections() -> None:
    evaluator = AnswerEvaluator()
    result = evaluator.evaluate(
        generated="Treatment includes 75 mg daily for 12 weeks with monitoring.",
        reference="Recommended treatment includes 75 mg daily and follow-up.",
        gt_key_phrases=["75 mg", "12 weeks", "treatment"],
    )
    payload = result.to_dict()
    assert "rouge" in payload
    assert "readability" in payload
    assert payload["key_info_recall"] >= 0.66

