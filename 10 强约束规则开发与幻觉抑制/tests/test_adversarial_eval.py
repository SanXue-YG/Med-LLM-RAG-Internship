"""Tests for adversarial evaluation (stage 5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

STAGE10 = Path(__file__).resolve().parents[1]
SRC = STAGE10 / "src"


@pytest.fixture(autouse=True)
def _paths():
    sys.path.insert(0, str(SRC))
    for name in ("config", "adversarial_eval", "citation_guard", "format_checker"):
        sys.modules.pop(name, None)
    from bootstrap import bootstrap_paths

    bootstrap_paths(STAGE10)
    yield


def _case(case_type: str, **kwargs):
    from adversarial_eval import AdversarialCase

    defaults = {
        "id": f"test_{case_type}",
        "query": "test query",
        "case_type": case_type,
        "expected_boundary_hit": False,
        "expected_behavior": "test",
    }
    defaults.update(kwargs)
    return AdversarialCase.from_dict(defaults)


def _result(
    *,
    answer: str,
    boundary_hit: bool = False,
    citation_ok: bool = True,
    format_ok: bool = True,
    extracted: list[int] | None = None,
    invalid: list[int] | None = None,
    abbrev_issues: list[str] | None = None,
) -> dict:
    return {
        "query": "q",
        "answer": answer,
        "constraint_checks": {
            "boundary_hit": boundary_hit,
            "citation": {
                "ok": citation_ok,
                "extracted": extracted or [],
                "invalid": invalid or [],
            },
            "format": {
                "ok": format_ok,
                "abbrev_issues": abbrev_issues or [],
            },
        },
    }


def test_load_adversarial_cases():
    from adversarial_eval import load_adversarial_cases

    cases = load_adversarial_cases(STAGE10 / "data" / "adversarial_cases.json")
    assert len(cases) == 5
    ids = {c.id for c in cases}
    assert "ood_2025_fda" in ids
    assert "normal_metformin" in ids


def test_score_ood_fail_without_refusal():
    from adversarial_eval import score_adversarial_case

    case = _case("ood", expected_boundary_hit=True)
    score = score_adversarial_case(case, _result(answer="Some answer.", boundary_hit=False))
    assert score.hallucination_fail is True
    assert score.in_hallucination_denominator is True
    assert "expected_boundary_refusal" in score.fail_reasons


def test_score_ood_pass_with_refusal():
    from adversarial_eval import score_adversarial_case

    case = _case("ood")
    answer = "Based on the provided literature, this question cannot be answered."
    score = score_adversarial_case(case, _result(answer=answer, boundary_hit=True))
    assert score.hallucination_fail is False


def test_score_fabrication_fail():
    from adversarial_eval import looks_like_fabrication, score_adversarial_case

    assert looks_like_fabrication("Side effects include nausea in 12% of patients.")
    case = _case("induce_fabrication")
    score = score_adversarial_case(
        case,
        _result(answer="Side effects include nausea in 12% of patients.", boundary_hit=False),
    )
    assert score.hallucination_fail is True


def test_score_fake_citation_fail():
    from adversarial_eval import score_adversarial_case

    case = _case("fake_citation")
    score = score_adversarial_case(
        case,
        _result(
            answer="Only [99].",
            citation_ok=False,
            extracted=[99],
            invalid=[99],
        ),
    )
    assert score.hallucination_fail is True


def test_score_normal_control_not_in_denominator():
    from adversarial_eval import aggregate_metrics, score_adversarial_case

    case = _case("normal_control")
    score = score_adversarial_case(
        case,
        _result(answer="**Answer:** ok [1]", citation_ok=True, format_ok=True, extracted=[1]),
    )
    assert score.in_hallucination_denominator is False
    metrics = aggregate_metrics([score])
    assert metrics.hallucination_denominator == 0
    assert metrics.hallucination_rate is None


def test_aggregate_metrics_full_batch():
    from adversarial_eval import aggregate_metrics, score_adversarial_case

    cases = [
        _case("ood", id="ood1"),
        _case("fake_citation", id="fake1"),
        _case("normal_control", id="norm1"),
    ]
    results = [
        _result(answer="refusal", boundary_hit=True),
        _result(answer="bad", citation_ok=False, invalid=[99]),
        _result(answer="good [1]", extracted=[1]),
    ]
    scores = [
        score_adversarial_case(c, r) for c, r in zip(cases, results, strict=True)
    ]
    metrics = aggregate_metrics(scores)
    assert metrics.total_cases == 3
    assert metrics.hallucination_denominator == 2
    assert metrics.hallucination_failures == 1
    assert metrics.hallucination_rate == 0.5
    assert metrics.refusal_hit_rate == 1.0
    assert metrics.format_compliance_rate == 1.0


def test_run_adversarial_eval_with_mock_fn():
    from adversarial_eval import load_adversarial_cases, run_adversarial_eval

    cases = load_adversarial_cases(STAGE10 / "data" / "adversarial_cases.json")[:2]

    def run_fn(case):
        if case.case_type == "ood":
            return _result(
                answer="Based on the provided literature, this question cannot be answered.",
                boundary_hit=True,
            )
        return _result(answer="Side effects include nausea.", boundary_hit=False)

    report = run_adversarial_eval(cases, run_fn)
    assert report["metrics"]["total_cases"] == 2
    assert "cases" in report
    assert report["cases"][0]["score"]["hallucination_fail"] is False


def test_citation_accuracy():
    from adversarial_eval import citation_accuracy_from_check

    assert citation_accuracy_from_check({"extracted": [1, 2], "invalid": []}) == 1.0
    assert citation_accuracy_from_check({"extracted": [1, 99], "invalid": [99]}) == 0.5
    assert citation_accuracy_from_check({"extracted": [], "invalid": []}) is None
