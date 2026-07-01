import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from postprocess import MEDICAL_DISCLAIMER, format_sources, postprocess_answer  # noqa: E402


def test_format_sources_required_fields():
    chunks = [
        {
            "chunk_id": "PMC_A",
            "relevance_score": 0.9,
            "metadata": {"source_title": "Study A", "doc_id": "PMC_A"},
            "text": "A",
        }
    ]
    sources = format_sources(chunks)
    assert sources[0]["index"] == 1
    assert sources[0]["chunk_id"] == "PMC_A"
    assert sources[0]["source_title"] == "Study A"
    assert sources[0]["doc_id"] == "PMC_A"
    assert sources[0]["relevance_score"] == 0.9


def test_postprocess_adds_refs_sources_and_disclaimer():
    sources = [
        {
            "index": 1,
            "chunk_id": "PMC_A",
            "source_title": "Study A",
            "doc_id": "PMC_A",
            "relevance_score": 0.9,
        },
        {
            "index": 2,
            "chunk_id": "PMC_B",
            "source_title": "Study B",
            "doc_id": "PMC_B",
            "relevance_score": 0.8,
        },
    ]
    text = postprocess_answer("Metformin may help.", sources)
    assert "Evidence refs: [1] [2]" in text
    assert "Sources:" in text
    assert "[1] Study A" in text
    assert MEDICAL_DISCLAIMER in text


def test_postprocess_keeps_existing_reference_markers():
    sources = [
        {
            "index": 1,
            "chunk_id": "PMC_A",
            "source_title": "Study A",
            "doc_id": "PMC_A",
            "relevance_score": 0.9,
        }
    ]
    text = postprocess_answer("Answer with [1] already.", sources)
    # 不应重复追加 Evidence refs
    assert text.count("Evidence refs:") <= 1
