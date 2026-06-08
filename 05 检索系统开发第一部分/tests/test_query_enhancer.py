import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from query_enhancer import MedicalQueryEnhancer  # noqa: E402


def test_mi_expansion():
    enh = MedicalQueryEnhancer()
    eq = enh.process("What is the treatment for MI?")
    joined = " ".join(eq.expanded_terms).lower()
    assert "myocardial infarction" in joined or "heart attack" in joined


def test_metformin_entity():
    enh = MedicalQueryEnhancer()
    eq = enh.process("metformin cardiovascular effects")
    types = {e.type for e in eq.entities}
    assert "drug" in types
    assert "metformin" in eq.keyword_query.lower()


def test_year_filter_not_executable():
    enh = MedicalQueryEnhancer()
    eq = enh.process("papers on malaria after 2015")
    year_filters = [f for f in eq.filters if f.key.startswith("year")]
    assert year_filters
    assert all(not f.executable for f in year_filters)


def test_strategy_executable():
    enh = MedicalQueryEnhancer()
    eq = enh.process("circadian rhythm sliding window chunks")
    strat = [f for f in eq.filters if f.key == "strategy"]
    assert strat and strat[0].value == "sliding_window"
    assert strat[0].executable


def test_vector_query_is_raw():
    enh = MedicalQueryEnhancer()
    q = "What is diabetes?"
    eq = enh.process(q)
    assert eq.vector_query == eq.cleaned
    assert "Represent this sentence" not in eq.vector_query


if __name__ == "__main__":
    test_mi_expansion()
    test_metformin_entity()
    test_year_filter_not_executable()
    test_strategy_executable()
    test_vector_query_is_raw()
    print("all tests passed")
