import json
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from rerank_features import (  # noqa: E402
    SlimMetadataLookup,
    authority_score,
    combine_criteria_scores,
    recency_score,
)


def test_recency_score_newer_is_higher():
    assert recency_score(2020) > recency_score(2000)
    assert recency_score(None) == 0.5


def test_recency_year_gte_penalty():
    assert recency_score(2010, year_gte=2015) < recency_score(2010)


def test_authority_nature():
    assert authority_score("Nature Medicine") >= 0.95
    assert authority_score("") == 0.5


def test_combine_criteria():
    s = combine_criteria_scores(0.8, 0.6, 0.4, {"relevance": 0.6, "recency": 0.25, "authority": 0.15})
    assert 0 < s <= 1


def test_slim_metadata_lookup_preload():
    rows = [
        {"pmcid": "PMC111", "pub_year": 2018, "journal": "Nature"},
        {"pmcid": "PMC222", "pub_year": 2015, "journal": "PLoS ONE"},
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        path = f.name
    try:
        lookup = SlimMetadataLookup(path)
        n = lookup.preload({"PMC111", "PMC222", "PMC999"})
        assert n == 2
        assert lookup.get("PMC111")["pub_year"] == 2018
        assert lookup.get("PMC999") is None
    finally:
        Path(path).unlink(missing_ok=True)
