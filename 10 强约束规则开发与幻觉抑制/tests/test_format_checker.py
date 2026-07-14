"""Tests for FormatChecker (stage 3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

STAGE10 = Path(__file__).resolve().parents[1]
SRC = STAGE10 / "src"


@pytest.fixture()
def checker():
    sys.path.insert(0, str(SRC))
    for name in ("config", "format_checker", "resources"):
        sys.modules.pop(name, None)
    from bootstrap import bootstrap_paths

    bootstrap_paths(STAGE10)
    from resources import load_medical_abbrev
    from format_checker import FormatChecker

    abbrevs = load_medical_abbrev(STAGE10)
    return FormatChecker(abbrevs, ref_strictness="relaxed")


def _good_answer():
    return (
        "**Answer:**\n"
        "MI (myocardial infarction) treatment includes reperfusion [1].\n\n"
        "**Evidence Summary:**\n"
        "- Reperfusion is discussed in [1].\n\n"
        "Sources:\n"
        "[1] Daily rhythms in homocysteine (doc_id=PMC520826, chunk_id=PMC520826, score=0.29)"
    )


def test_good_answer_passes(checker):
    result = checker.check(_good_answer())
    assert result.ok is True
    assert result.boundary_hit is False
    assert all(result.sections_found.values())


def test_missing_section_fails(checker):
    answer = "**Answer:**\nMI (myocardial infarction) only.\n"
    result = checker.check(answer)
    assert result.ok is False
    assert any("Evidence Summary" in i for i in result.issues)
    assert any("References" in i for i in result.issues)


def test_boundary_hit_exempts_sections(checker):
    refusal = checker.refusal_en
    result = checker.check(refusal)
    assert result.boundary_hit is True
    assert result.ok is True
    assert result.issues == []


def test_bare_abbrev_without_expansion_fails(checker):
    answer = (
        "**Answer:**\n"
        "MI treatment is discussed [1].\n\n"
        "**Evidence Summary:**\n- x\n\n"
        "Sources:\n[1] Some paper (doc_id=PMC1)"
    )
    result = checker.check(answer)
    assert result.ok is False
    assert any("MI" in i for i in result.abbrev_issues)


def test_relaxed_missing_year_warn_only(checker):
    sources = [
        {
            "index": 1,
            "source_title": "Metformin study",
            "doc_id": "PMC1",
            "chunk_id": "PMC1",
        }
    ]
    answer = _good_answer()
    result = checker.check(answer, sources=sources)
    assert result.ok is True
    assert any("year" in w.lower() for w in result.warnings)


def test_strict_missing_year_fails():
    sys.path.insert(0, str(STAGE10 / "src"))
    from format_checker import FormatChecker

    strict = FormatChecker({"MI": "myocardial infarction"}, ref_strictness="strict")
    sources = [{"index": 1, "source_title": "Paper A", "doc_id": "PMC1"}]
    answer = _good_answer()
    result = strict.check(answer, sources=sources)
    assert result.ok is False
    assert any("year" in i.lower() for i in result.issues)


def test_soft_patch_adds_missing_headings(checker):
    answer = "MI (myocardial infarction) only body."
    result = checker.check(answer)
    assert result.ok is False
    patched, changed = checker.soft_patch(answer, result)
    assert changed is True
    assert "**Answer:**" in patched
    assert "Evidence Summary" in patched
    assert "Sources" in patched


def test_boundary_soft_patch_noop(checker):
    result = checker.check(checker.refusal_en)
    patched, changed = checker.soft_patch(checker.refusal_en, result)
    assert changed is False
    assert patched == checker.refusal_en
