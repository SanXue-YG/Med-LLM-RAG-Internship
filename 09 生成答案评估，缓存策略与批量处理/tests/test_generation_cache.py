from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from generation_cache import GenerationCache


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def test_make_key_is_stable_for_same_input() -> None:
    cache = GenerationCache()
    k1 = cache.make_key("q", "ctx", "deepseek-r1:7b", 0.2)
    k2 = cache.make_key("q", "ctx", "deepseek-r1:7b", 0.2)
    assert k1 == k2


def test_ttl_expiration_returns_none() -> None:
    clock = FakeClock()
    cache = GenerationCache(ttl_seconds=10, now_fn=clock.now)
    key = cache.make_key("q", "ctx", "m", 0.2)
    cache.set(key, {"answer": "ok"}, temperature=0.2)
    assert cache.get(key) == {"answer": "ok"}
    clock.advance(11)
    assert cache.get(key) is None


def test_high_temperature_is_not_cached() -> None:
    cache = GenerationCache(max_temperature=0.3)
    key = cache.make_key("q", "ctx", "m", 0.8)
    cached = cache.set(key, {"answer": "hot"}, temperature=0.8)
    assert cached is False
    assert cache.get(key) is None


def test_lru_eviction_happens_when_full() -> None:
    cache = GenerationCache(max_entries=2, ttl_seconds=1000)
    k1 = cache.make_key("q1", "ctx", "m", 0.1)
    k2 = cache.make_key("q2", "ctx", "m", 0.1)
    k3 = cache.make_key("q3", "ctx", "m", 0.1)
    cache.set(k1, {"n": 1}, temperature=0.1)
    cache.set(k2, {"n": 2}, temperature=0.1)
    _ = cache.get(k1)  # make k1 recent
    cache.set(k3, {"n": 3}, temperature=0.1)  # evict k2
    assert cache.get(k1) == {"n": 1}
    assert cache.get(k2) is None
    assert cache.get(k3) == {"n": 3}
    assert cache.stats()["evictions"] == 1

