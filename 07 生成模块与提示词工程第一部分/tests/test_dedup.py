import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from context_assembler import ContextAssembler  # noqa: E402
from models import DocumentChunk, coerce_to_document_chunks  # noqa: E402


def _chunk(text: str, score: float, cid: str, doc_id: str | None = None) -> DocumentChunk:
    return DocumentChunk(
        text=text,
        metadata={"doc_id": doc_id or cid, "source_title": f"title-{cid}"},
        relevance_score=score,
        source=f"title-{cid}",
        chunk_id=cid,
    )


def test_dedup_keeps_higher_relevance_chunk():
    asm = ContextAssembler(tokenizer_name=None, dedup_threshold=0.85)
    text = "metformin cardiovascular effects trial results showed improvement"
    chunks = [
        _chunk(text, 0.5, "c2"),
        _chunk(text, 1.0, "c1"),
    ]
    out = asm.dedup_by_jaccard(chunks)
    assert len(out) == 1
    assert out[0].chunk_id == "c1"


def test_dedup_respects_threshold_boundary():
    text_a = "warfarin dosing elderly patients atrial fibrillation guidelines"
    text_b = "warfarin dosing elderly patients atrial fibrillation guidelines revised"
    chunks = [_chunk(text_a, 1.0, "c1"), _chunk(text_b, 0.5, "c2")]

    strict = ContextAssembler(tokenizer_name=None, dedup_threshold=1.0)
    assert len(strict.dedup_by_jaccard(chunks)) == 2

    loose = ContextAssembler(tokenizer_name=None, dedup_threshold=0.5)
    out = loose.dedup_by_jaccard(chunks)
    assert len(out) == 1
    assert out[0].chunk_id == "c1"


def test_dedup_keeps_both_when_dissimilar():
    asm = ContextAssembler(tokenizer_name=None, dedup_threshold=0.85)
    chunks = [
        _chunk("malaria vaccine efficacy in children", 0.9, "a"),
        _chunk("warfarin atrial fibrillation elderly dosing", 0.8, "b"),
    ]
    out = asm.dedup_by_jaccard(chunks)
    assert len(out) == 2


def test_dedup_empty_list():
    asm = ContextAssembler(tokenizer_name=None)
    assert asm.dedup_by_jaccard([]) == []


def test_coerce_skips_invalid_text():
    good = _chunk("valid chunk text here", 0.5, "ok")
    chunks, skipped = coerce_to_document_chunks([
        {"text": ""},
        {"text": 123},
        good,
    ])
    assert len(chunks) == 1
    assert skipped == 2
    assert chunks[0].chunk_id == "ok"


def test_diversity_penalizes_same_doc_id():
    asm = ContextAssembler(tokenizer_name=None, max_per_source=1, source_penalty=0.5)
    chunks = [
        _chunk("topic alpha one", 0.9, "a1", "DOC_A"),
        _chunk("topic alpha two", 0.85, "a2", "DOC_A"),
        _chunk("topic beta one", 0.8, "b1", "DOC_B"),
    ]
    ordered = asm._order_with_diversity(chunks)
    doc_ids = [c.metadata["doc_id"] for c in ordered[:2]]
    assert doc_ids[0] != doc_ids[1]
