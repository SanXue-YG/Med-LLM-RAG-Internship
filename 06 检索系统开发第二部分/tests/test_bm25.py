import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from bm25_index import BM25Index, tokenize  # noqa: E402
from config import resolve_chunks_path  # noqa: E402


def test_tokenize_lowercase_and_stopwords():
    tokens = tokenize("The Malaria vaccine in 2015")
    assert "the" not in tokens
    assert "in" not in tokens
    assert "malaria" in tokens
    assert "vaccine" in tokens
    assert "2015" in tokens


def test_tokenize_keeps_numeric_medical_tokens():
    tokens = tokenize("metformin h1n1 covid19")
    assert "metformin" in tokens
    assert "h1n1" in tokens
    assert "covid19" in tokens


def test_build_sample_index():
    idx = BM25Index()
    n = idx.build(mode="sample")
    assert n == 1267
    assert idx.size == 1267
    assert idx.source_path == resolve_chunks_path("sample").resolve()


def test_search_malaria():
    idx = BM25Index()
    idx.build(mode="sample")
    hits = idx.search("malaria plasmodium falciparum", top_k=5)
    assert hits
    assert hits[0]["source"] == "bm25"
    assert hits[0]["rank"] == 1
    assert "chunk_id" in hits[0]
    assert hits[0]["score"] > 0
    top_ids = {h["chunk_id"] for h in hits}
    assert "PMC176545" in top_ids


def test_search_circadian_sliding_window():
    idx = BM25Index()
    idx.build(mode="sample")
    hits = idx.search("circadian rhythm drosophila", top_k=5)
    assert hits
    doc_ids = {h["doc_id"] for h in hits}
    assert "PMC193604" in doc_ids


def test_output_candidate_fields():
    idx = BM25Index()
    idx.build(mode="sample")
    hit = idx.search("metformin cardiovascular", top_k=1)[0]
    for key in ("chunk_id", "doc_id", "source_title", "text", "source", "score", "rank"):
        assert key in hit
    assert hit["source"] == "bm25"
    assert isinstance(hit["score"], float)
    assert hit["rank"] == 1


def test_top_k_respected():
    idx = BM25Index()
    idx.build(mode="sample")
    hits = idx.search("gene expression", top_k=3)
    assert len(hits) <= 3
    assert [h["rank"] for h in hits] == list(range(1, len(hits) + 1))
