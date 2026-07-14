"""Tests for CitationGuard (stage 2)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

STAGE10 = Path(__file__).resolve().parents[1]
SRC = STAGE10 / "src"


@pytest.fixture()
def guard():
    sys.path.insert(0, str(SRC))
    for name in ("config", "citation_guard"):
        sys.modules.pop(name, None)
    from bootstrap import bootstrap_paths

    bootstrap_paths(STAGE10)
    from citation_guard import CitationGuard

    return CitationGuard(missing_policy="warn")


def _chunks():
    return [
        {"text": "Metformin improves cardiovascular outcomes.", "chunk_id": "PMC1"},
        {"text": "AMPK activation reduces fibrosis.", "chunk_id": "PMC2"},
        {"text": "Bleeding risk must be monitored.", "chunk_id": "PMC3"},
    ]


def test_assign_labels_rebuilds_context_and_valid_ids(guard):
    labeled = guard.assign_labels(_chunks())
    assert labeled.valid_ids == {1, 2, 3}
    assert labeled.context_text.startswith("[1] Metformin")
    assert "[2] AMPK" in labeled.context_text
    assert "[3] Bleeding" in labeled.context_text
    assert len(labeled.selected_chunks) == 3
    assert labeled.selected_chunks[0]["metadata"]["citation_index"] == 1


def test_extract_citations_canonical_and_chinese(guard):
    answer = "Effect noted [1]. Also 文献2 and [文献3]."
    assert guard.extract_citations(answer) == [1, 2, 3]


def test_validate_legal_citations_pass(guard):
    answer = "**Answer:** Metformin helps [1]. Evidence [2]."
    result = guard.validate(answer, {1, 2, 3})
    assert result.ok is True
    assert result.extracted == [1, 2]
    assert result.invalid == []


def test_validate_invalid_citation_fails(guard):
    answer = "Please cite [99] only for this claim."
    result = guard.validate(answer, {1, 2, 3})
    assert result.ok is False
    assert result.invalid == [99]
    assert any("Invalid citation" in i for i in result.issues)


def test_validate_missing_citations_warn_not_fail(guard):
    answer = "Metformin improves outcomes without any citation markers."
    result = guard.validate(answer, {1, 2})
    assert result.ok is True
    assert result.warnings
    assert "No citation markers" in result.warnings[0]


def test_validate_missing_citations_fail_when_policy_fail():
    sys.path.insert(0, str(SRC))
    from citation_guard import CitationGuard

    strict = CitationGuard(missing_policy="fail")
    answer = "Metformin improves outcomes without markers."
    result = strict.validate(answer, {1, 2})
    assert result.ok is False
    assert result.issues


def test_retry_or_repair_strips_invalid_markers(guard):
    answer = "Claim A [1] and bogus [99] here."
    check = guard.validate(answer, {1, 2})
    repaired, did = guard.retry_or_repair(answer, check)
    assert did is True
    assert "[99]" not in repaired
    assert "[1]" in repaired
    recheck = guard.validate(repaired, {1, 2})
    assert recheck.invalid == []


def test_build_retry_hint_lists_invalid_ids(guard):
    check = guard.validate("bad [99]", {1, 2})
    hint = guard.build_retry_hint(check)
    assert "99" in hint
    assert "[1, 2]" in hint or "1, 2" in hint


def test_extract_ignores_sources_block(guard):
    answer = (
        "**Answer:** Supported [1].\n\n"
        "Sources:\n[1] Some paper (doc_id=PMC1)\n[99] should not count"
    )
    # [99] in Sources block should not be extracted
    assert guard.extract_citations(answer) == [1]
