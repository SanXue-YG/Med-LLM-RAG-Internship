"""Generation cache for stage 09.

Current boundary:
- In-memory only (process lifetime).
- Data is lost after process exit.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def _load_stage09_default_config() -> Any:
    """Always load local stage09 config to avoid cross-stage name collisions."""
    config_path = Path(__file__).with_name("config.py")
    spec = importlib.util.spec_from_file_location("stage09_local_config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load config from {config_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.DEFAULT_CONFIG


DEFAULT_CONFIG = _load_stage09_default_config()


@dataclass
class CacheEntry:
    value: dict[str, Any]
    expires_at: float


class BaseCacheBackend:
    """Backend interface placeholder for future sqlite/redis extension."""

    def get(self, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def set(self, key: str, value: dict[str, Any], *, ttl_seconds: int) -> bool:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def keys(self) -> list[str]:
        raise NotImplementedError


class MemoryCacheBackend(BaseCacheBackend):
    """Simple in-memory backend with OrderedDict storage."""

    def __init__(self) -> None:
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._store.get(key)
        return None if entry is None else entry.value

    def set(self, key: str, value: dict[str, Any], *, ttl_seconds: int) -> bool:
        _ = ttl_seconds
        self._store[key] = CacheEntry(value=value, expires_at=0.0)
        return True

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def keys(self) -> list[str]:
        return list(self._store.keys())


class GenerationCache:
    def __init__(
        self,
        *,
        max_entries: int | None = None,
        ttl_seconds: int | None = None,
        max_temperature: float | None = None,
        now_fn: Callable[[], float] | None = None,
        backend: BaseCacheBackend | None = None,
    ) -> None:
        self.max_entries = max_entries if max_entries is not None else DEFAULT_CONFIG.max_entries
        self.ttl_seconds = ttl_seconds if ttl_seconds is not None else DEFAULT_CONFIG.ttl_seconds
        self.max_temperature = (
            max_temperature if max_temperature is not None else DEFAULT_CONFIG.max_temperature
        )
        self._now_fn = now_fn or time.time
        self._backend = backend or MemoryCacheBackend()

        # Local index for LRU/TTL management; backend stays abstract.
        self._index: OrderedDict[str, CacheEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def make_key(self, query: str, context_text: str, model: str, temperature: float) -> str:
        payload = {
            "query": query.strip(),
            "context_text": context_text.strip(),
            "model": model.strip(),
            "temperature_bucket": round(float(temperature), 2),
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        self._cleanup_expired_key(key)
        entry = self._index.get(key)
        if entry is None:
            self.misses += 1
            return None

        self._index.move_to_end(key)
        self.hits += 1
        return entry.value

    def set(self, key: str, value: dict[str, Any], *, temperature: float) -> bool:
        if float(temperature) > self.max_temperature:
            return False

        expires_at = self._now_fn() + self.ttl_seconds
        copied = dict(value)
        self._index[key] = CacheEntry(value=copied, expires_at=expires_at)
        self._index.move_to_end(key)

        while len(self._index) > self.max_entries:
            self._index.popitem(last=False)
            self.evictions += 1
        return True

    def delete(self, key: str) -> None:
        self._index.pop(key, None)
        self._backend.delete(key)

    def stats(self) -> dict[str, int]:
        self._cleanup_expired_all()
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "size": len(self._index),
        }

    def _cleanup_expired_key(self, key: str) -> None:
        entry = self._index.get(key)
        if entry is None:
            return
        if entry.expires_at <= self._now_fn():
            self._index.pop(key, None)

    def _cleanup_expired_all(self) -> None:
        now = self._now_fn()
        expired = [k for k, v in self._index.items() if v.expires_at <= now]
        for key in expired:
            self._index.pop(key, None)

