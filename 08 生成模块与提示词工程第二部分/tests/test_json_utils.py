import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from json_utils import (  # noqa: E402
    extract_json,
    filter_chunks_by_evidence_eval,
    normalize_evidence_evaluation,
    parse_evidence_evaluation,
    repair_json,
)


def test_extract_json_from_markdown_fence():
    raw = 'Here is output:\n```json\n{"relevant_chunk_ids": ["A"], "notes": "ok"}\n```'
    assert extract_json(raw) == {"relevant_chunk_ids": ["A"], "notes": "ok"}


def test_repair_json_missing_closing_brace():
    broken = '{"relevant_chunk_ids": ["PMC1"], "notes": "weak"'
    repaired = repair_json(broken)
    assert extract_json(repaired) == {
        "relevant_chunk_ids": ["PMC1"],
        "notes": "weak",
    }


def test_repair_json_trailing_comma():
    broken = '{"excluded_chunk_ids": ["PMC2",], "notes": ""}'
    assert extract_json(broken) == {"excluded_chunk_ids": ["PMC2"], "notes": ""}


def test_parse_evidence_evaluation_normalizes_fields():
    text = """```json
    {
      "relevant_chunk_ids": "PMC100",
      "excluded_chunk_ids": ["PMC200", "PMC201"],
      "notes": 123
    }
    ```"""
    parsed = parse_evidence_evaluation(text)
    assert parsed == {
        "relevant_chunk_ids": ["PMC100"],
        "excluded_chunk_ids": ["PMC200", "PMC201"],
        "notes": "123",
    }


def test_filter_chunks_none_evaluation_returns_all():
    chunks = [{"chunk_id": "A"}, {"chunk_id": "B"}]
    assert filter_chunks_by_evidence_eval(chunks, None) == chunks


def test_filter_chunks_by_relevant_ids():
    chunks = [{"chunk_id": "A"}, {"chunk_id": "B"}, {"chunk_id": "C"}]
    evaluation = {
        "relevant_chunk_ids": ["A", "C"],
        "excluded_chunk_ids": [],
        "notes": "",
    }
    assert filter_chunks_by_evidence_eval(chunks, evaluation) == [
        {"chunk_id": "A"},
        {"chunk_id": "C"},
    ]


def test_filter_chunks_by_excluded_ids():
    chunks = [{"chunk_id": "A"}, {"chunk_id": "B"}]
    evaluation = {
        "relevant_chunk_ids": [],
        "excluded_chunk_ids": ["B"],
        "notes": "drop B",
    }
    assert filter_chunks_by_evidence_eval(chunks, evaluation) == [{"chunk_id": "A"}]


def test_normalize_evidence_evaluation_invalid():
    assert normalize_evidence_evaluation(None) is None
    assert normalize_evidence_evaluation([]) is None
