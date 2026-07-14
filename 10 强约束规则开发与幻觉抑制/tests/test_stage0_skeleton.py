"""Lightweight stage-0 sanity checks (no Ollama / full corpus required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

STAGE10 = Path(__file__).resolve().parents[1]


@pytest.fixture()
def boot():
    sys.path.insert(0, str(STAGE10 / "src"))
    # Clear cached name-colliding modules from other stages.
    for name in ("config", "bootstrap", "resources"):
        sys.modules.pop(name, None)
    from bootstrap import bootstrap_paths

    return bootstrap_paths(STAGE10)


def test_bootstrap_inserts_stage_srcs(boot):
    assert boot["stage10"].name.startswith("10")
    assert Path(sys.path[0]).resolve() == (boot["stage10"] / "src").resolve()
    assert (boot["stage06"] / "src").is_dir()


def test_config_defaults_full_first(boot):
    sys.modules.pop("config", None)
    from config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG.retrieval_mode == "full"
    assert DEFAULT_CONFIG.max_retries == 1
    assert DEFAULT_CONFIG.ref_strictness == "relaxed"
    assert "literature" in DEFAULT_CONFIG.refusal_en.lower()


def test_medical_abbrev_loads(boot):
    from resources import load_medical_abbrev

    abbrevs = load_medical_abbrev(STAGE10)
    for key in ("MI", "AF", "HF", "T2DM", "TAVR"):
        assert key in abbrevs
        assert len(abbrevs[key]) > 2


def test_medical_abbrev_json_shape():
    path = STAGE10 / "data" / "medical_abbrev.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == "stage10-v1"
    assert isinstance(payload["abbreviations"], dict)
    assert len(payload["abbreviations"]) >= 10
