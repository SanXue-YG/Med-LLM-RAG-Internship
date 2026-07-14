"""Tests for ConstraintPromptBundle (stage 1)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

STAGE10 = Path(__file__).resolve().parents[1]
SRC = STAGE10 / "src"


@pytest.fixture()
def bundle():
    sys.path.insert(0, str(SRC))
    for name in ("config", "constraint_prompts"):
        sys.modules.pop(name, None)
    from bootstrap import bootstrap_paths

    bootstrap_paths(STAGE10)
    from constraint_prompts import default_constraint_bundle

    return default_constraint_bundle()


def test_layers_non_empty(bundle):
    layers = bundle.layer_dict()
    assert len(layers) == 4
    for name, text in layers.items():
        assert text.strip(), f"{name} should not be empty"


def test_as_system_prompt_contains_refusal_keywords(bundle):
    text = bundle.as_system_prompt()
    assert "KNOWLEDGE BOUNDARY" in text
    assert bundle.refusal_en in text
    assert bundle.refusal_zh in text
    assert "provided literature" in text.lower()


def test_as_system_prompt_contains_citation_rules(bundle):
    text = bundle.as_system_prompt()
    assert "CITATION RULES" in text
    assert "[1]" in text
    assert "outside the assigned range" in text.lower() or "never cite" in text.lower()


def test_as_system_prompt_contains_no_fabrication(bundle):
    text = bundle.as_system_prompt()
    assert "NO FABRICATION" in text
    assert "not explicitly supported" in text.lower()


def test_as_system_prompt_contains_format_rules(bundle):
    text = bundle.as_system_prompt()
    assert "OUTPUT FORMAT" in text
    assert "Evidence Summary" in text
    assert "Sources" in text


def test_append_to_preserves_original_system(bundle):
    original = "You are a cautious medical assistant."
    merged = bundle.append_to(original)
    assert merged.startswith(original)
    assert bundle.refusal_en in merged
    assert "HARD CONSTRAINTS" in merged


def test_append_to_empty_base_returns_constraints_only(bundle):
    merged = bundle.append_to("")
    assert merged == bundle.as_system_prompt()


def test_append_to_does_not_drop_stage07_style_prompt(bundle):
    stage07_system = (
        "You are a final response assembler for medical QA. "
        "Produce clear, structured, and risk-aware final output."
    )
    merged = bundle.append_to(stage07_system)
    assert stage07_system in merged
    assert merged.index(stage07_system) < merged.index("HARD CONSTRAINTS")
