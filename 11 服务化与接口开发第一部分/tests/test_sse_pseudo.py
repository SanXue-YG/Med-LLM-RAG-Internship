"""Unit tests for pseudo-SSE chunking helpers."""

from app.services.sse_pseudo import chunk_answer_pseudo, format_sse


def test_format_sse_shape():
    msg = format_sse("meta", {"stream_mode": "pseudo"})
    assert msg.startswith("event: meta\n")
    assert 'data: {"stream_mode": "pseudo"}' in msg
    assert msg.endswith("\n\n")


def test_chunk_empty():
    assert chunk_answer_pseudo("") == []


def test_chunk_by_sentence_and_window():
    text = "Hello world. Next sentence!"
    parts = chunk_answer_pseudo(text, window=8)
    assert "".join(parts) == text
    assert len(parts) >= 2

    long = "a" * 50
    parts2 = chunk_answer_pseudo(long, window=10)
    assert "".join(parts2) == long
    assert all(len(p) <= 10 for p in parts2)
