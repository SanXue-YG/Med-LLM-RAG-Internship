import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from context_assembler import ContextAssembler  # noqa: E402
from models import DocumentChunk  # noqa: E402


def _chunk(text: str, score: float, cid: str) -> DocumentChunk:
    return DocumentChunk(
        text=text,
        metadata={"doc_id": cid},
        relevance_score=score,
        source=f"source-{cid}",
        chunk_id=cid,
    )


def test_estimate_tokens_heuristic():
    asm = ContextAssembler(tokenizer_name=None)
    assert asm.estimate_tokens("") == 0
    assert asm.estimate_tokens("abcd") == 1


def test_truncate_at_sentence_boundary_in_last_ten_percent():
    asm = ContextAssembler(tokenizer_name=None)
    text = "A" * 175 + "End sentence."
    truncated = asm._truncate_at_sentence_boundary(text)
    assert truncated.endswith(".")


def test_truncate_to_tokens_respects_limit():
    asm = ContextAssembler(tokenizer_name=None)
    text = "word " * 200
    out = asm._truncate_to_tokens(text, 30)
    assert asm.estimate_tokens(out) <= 30


def test_assemble_respects_max_context_tokens():
    asm = ContextAssembler(tokenizer_name=None)
    chunks = [
        _chunk("paragraph one " * 80, 1.0, "c1"),
        _chunk("paragraph two " * 80, 0.9, "c2"),
        _chunk("paragraph three " * 80, 0.8, "c3"),
    ]
    result = asm.assemble(chunks, max_context_tokens=120)
    assert result.metadata.estimated_tokens <= 120
    assert result.metadata.chunks_selected >= 1
    assert result.context_text


def test_assemble_metadata_fields():
    asm = ContextAssembler(tokenizer_name=None)
    chunks = [_chunk("single chunk content", 0.5, "only")]
    result = asm.assemble(chunks, max_context_tokens=500)
    meta = result.metadata
    assert meta.total_chunks_retrieved == 1
    assert meta.unique_chunks_after_dedup == 1
    assert meta.chunks_selected == 1
    assert meta.estimated_tokens > 0
    assert "counts" in meta.chunk_sources
