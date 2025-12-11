import pickle
from datetime import datetime, timedelta

import pytest

from src.utils import semantic_cache


class FakeRedis:
    def __init__(self):
        self.store = {}

    def setex(self, key, ttl, value):
        self.store[key] = (value, ttl)

    def get(self, key):
        val = self.store.get(key)
        if val is None:
            return None
        return val[0]

    def scan_iter(self, match=None):
        for k in list(self.store.keys()):
            yield k

    def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)


def test_semantic_cache_memory_fallback(monkeypatch):
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: None)
    semantic_cache.clear_semantic_cache()
    semantic_cache.set_semantic_cached_result("q1", "res1", "sql1", ttl_seconds=10)
    hit = semantic_cache.get_semantic_cached_result("q1")
    assert hit is not None
    assert hit[0] == "res1"
    semantic_cache.clear_semantic_cache()


def test_semantic_cache_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: fake)
    semantic_cache.clear_semantic_cache()

    semantic_cache.set_semantic_cached_result("q1", "res1", "sql1", ttl_seconds=10)
    # Construir entrada manualmente para simular expiración
    for key, (val, ttl) in list(fake.store.items()):
        entry = pickle.loads(val)
        entry["expires_at"] = datetime.now() + timedelta(seconds=10)
        fake.store[key] = (pickle.dumps(entry), ttl)

    hit = semantic_cache.get_semantic_cached_result("q1")
    assert hit is not None
    assert hit[0] == "res1"

    semantic_cache.clear_semantic_cache()
