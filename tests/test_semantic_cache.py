import pickle
import sys
from types import SimpleNamespace
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
    monkeypatch.setattr(semantic_cache, "_get_embedding_model", lambda: object())
    monkeypatch.setattr(semantic_cache, "_compute_embedding", lambda text: [1.0, 0.0])
    semantic_cache.clear_semantic_cache()
    semantic_cache.set_semantic_cached_result("q1", "res1", "sql1", ttl_seconds=10)
    hit = semantic_cache.get_semantic_cached_result("q1")
    assert hit is not None
    assert hit[0] == "res1"
    semantic_cache.clear_semantic_cache()


def test_semantic_cache_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: fake)
    monkeypatch.setattr(semantic_cache, "_get_embedding_model", lambda: object())
    monkeypatch.setattr(semantic_cache, "_compute_embedding", lambda text: [1.0, 0.0])
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


def test_set_semantic_cache_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: None)
    monkeypatch.setattr(semantic_cache, "_get_embedding_model", lambda: object())
    monkeypatch.setattr(semantic_cache, "_compute_embedding", lambda text: [1.0, 0.0])
    semantic_cache.clear_semantic_cache()

    semantic_cache.set_semantic_cached_result("q", "r", "sql")
    assert semantic_cache._semantic_cache == {}


def test_set_semantic_cache_noop_when_model_missing(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")
    monkeypatch.setattr(semantic_cache, "_get_embedding_model", lambda: None)
    semantic_cache.clear_semantic_cache()

    semantic_cache.set_semantic_cached_result("q", "r", "sql")
    assert semantic_cache._semantic_cache == {}


def test_set_semantic_cache_redis_failure_falls_back(monkeypatch):
    class BadRedis(FakeRedis):
        def setex(self, *a, **k):
            raise Exception("fail")

    bad = BadRedis()
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: bad)
    monkeypatch.setattr(semantic_cache, "_get_embedding_model", lambda: object())
    monkeypatch.setattr(semantic_cache, "_compute_embedding", lambda text: [1.0, 0.0])
    semantic_cache.clear_semantic_cache()

    semantic_cache.set_semantic_cached_result("q1", "res1", "sql1", ttl_seconds=10)
    assert semantic_cache._semantic_cache  # fallback a memoria


def test_get_semantic_cache_stats_handles_redis_scan_error(monkeypatch):
    class BadRedis:
        def scan_iter(self, *a, **k):
            raise Exception("boom")

    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: BadRedis())
    stats = semantic_cache.get_semantic_cache_stats()
    assert stats["total_entries_redis"] == 0


def test_cleanup_expired_semantic_cache_removes_memory_entries(monkeypatch):
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: None)
    semantic_cache.clear_semantic_cache()

    semantic_cache._semantic_cache["a"] = {
        "result": "old",
        "sql": "s",
        "embedding": [0.0],
        "expires_at": datetime.now() - timedelta(seconds=1),
    }
    semantic_cache._semantic_cache["b"] = {
        "result": "new",
        "sql": "s",
        "embedding": [0.0],
        "expires_at": datetime.now() + timedelta(seconds=60),
    }

    semantic_cache.cleanup_expired_semantic_cache()
    assert "a" not in semantic_cache._semantic_cache
    assert "b" in semantic_cache._semantic_cache


def test_preload_embedding_model_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")
    semantic_cache._embedding_model = None
    assert semantic_cache.preload_embedding_model() is False


def test_preload_embedding_model_returns_true_if_already_loaded(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")
    semantic_cache._embedding_model = object()
    assert semantic_cache.preload_embedding_model() is True


def test_preload_embedding_model_import_error(monkeypatch):
    semantic_cache._embedding_model = None
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("sentence_transformers"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    assert semantic_cache.preload_embedding_model() is False


def test_get_embedding_model_import_error(monkeypatch):
    semantic_cache._embedding_model = None
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("sentence_transformers"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    assert semantic_cache._get_embedding_model() is None


def test_compute_embedding_uses_cache(monkeypatch):
    semantic_cache._embedding_cache.clear()

    class DummyModel:
        def __init__(self):
            self.calls = 0

        def encode(self, text, **kwargs):
            self.calls += 1
            return [1.0, 0.0]

    dummy = DummyModel()
    monkeypatch.setattr(semantic_cache, "_get_embedding_model", lambda: dummy)

    emb1 = semantic_cache._compute_embedding("q")
    emb2 = semantic_cache._compute_embedding("q")
    assert emb1 == emb2
    assert dummy.calls == 1


def test_compute_embedding_returns_none_when_model_missing(monkeypatch):
    semantic_cache._embedding_cache.clear()
    monkeypatch.setattr(semantic_cache, "_get_embedding_model", lambda: None)
    assert semantic_cache._compute_embedding("q") is None


def test_compute_embedding_handles_encode_exception(monkeypatch):
    semantic_cache._embedding_cache.clear()

    class BadModel:
        def encode(self, *a, **k):
            raise Exception("boom")

    monkeypatch.setattr(semantic_cache, "_get_embedding_model", lambda: BadModel())
    assert semantic_cache._compute_embedding("q") is None


def test_compute_similarity_zero_norm_returns_zero():
    assert semantic_cache._compute_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_compute_similarity_handles_import_error(monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("numpy"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    assert semantic_cache._compute_similarity([1.0], [1.0]) == 0.0


def test_preload_embedding_model_success_with_dummy(monkeypatch):
    """Cubre rama exitosa de preload_embedding_model sin descargar modelos."""
    semantic_cache._embedding_model = None
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")

    class DummyST:
        def __init__(self, name):
            pass

    dummy_module = SimpleNamespace(SentenceTransformer=DummyST)
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy_module)

    assert semantic_cache.preload_embedding_model() is True
    assert semantic_cache._embedding_model is not None


def test_preload_embedding_model_handles_generic_exception(monkeypatch):
    semantic_cache._embedding_model = None
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")

    class BadST:
        def __init__(self, name):
            raise Exception("boom")

    dummy_module = SimpleNamespace(SentenceTransformer=BadST)
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy_module)

    assert semantic_cache.preload_embedding_model() is False


def test_get_embedding_model_success_with_dummy(monkeypatch):
    """Cubre rama exitosa de _get_embedding_model."""
    semantic_cache._embedding_model = None

    class DummyST:
        def __init__(self, name):
            pass

    dummy_module = SimpleNamespace(SentenceTransformer=DummyST)
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy_module)

    assert semantic_cache._get_embedding_model() is not None


def test_get_embedding_model_handles_generic_exception(monkeypatch):
    semantic_cache._embedding_model = None

    class BadST:
        def __init__(self, name):
            raise Exception("boom")

    dummy_module = SimpleNamespace(SentenceTransformer=BadST)
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy_module)

    assert semantic_cache._get_embedding_model() is None


def test_compute_similarity_converts_numpy_tensors():
    import numpy as np

    class DummyTensor:
        def __init__(self, arr):
            self._arr = arr

        def numpy(self):
            return self._arr

    emb = DummyTensor(np.array([1.0, 0.0]))
    assert semantic_cache._compute_similarity(emb, emb) == pytest.approx(1.0)


def test_get_semantic_cached_result_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")
    assert semantic_cache.get_semantic_cached_result("q") is None


def test_get_semantic_cached_result_miss_skips_expired_and_missing_embedding(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: None)
    monkeypatch.setattr(semantic_cache, "_compute_embedding", lambda _q: [1.0, 0.0])
    semantic_cache.clear_semantic_cache()

    now = datetime.now()
    semantic_cache._semantic_cache["expired"] = {
        "result": "old",
        "sql": "s",
        "embedding": [1.0, 0.0],
        "expires_at": now - timedelta(seconds=1),
    }
    semantic_cache._semantic_cache["no_emb"] = {
        "result": "x",
        "sql": "s",
        "expires_at": now + timedelta(seconds=10),
    }

    assert semantic_cache.get_semantic_cached_result("q") is None


def test_get_semantic_cached_result_redis_scan_exception_falls_back_to_memory(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")

    class BadRedis:
        def scan_iter(self, *a, **k):
            raise Exception("boom")

    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: BadRedis())
    monkeypatch.setattr(semantic_cache, "_compute_embedding", lambda _q: [1.0, 0.0])
    semantic_cache.clear_semantic_cache()

    semantic_cache._semantic_cache["ok"] = {
        "result": "res",
        "sql": "sql",
        "embedding": [1.0, 0.0],
        "expires_at": datetime.now() + timedelta(seconds=10),
    }

    hit = semantic_cache.get_semantic_cached_result("q")
    assert hit == ("res", "sql")


def test_get_semantic_cached_result_redis_skips_missing_data_and_embedding(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")

    class RedisWithWeirdEntries(FakeRedis):
        def __init__(self):
            super().__init__()
            self.store["semantic:a"] = (None, 10)
            self.store["semantic:b"] = (pickle.dumps({"result": "x"}), 10)

    # Limpiar memoria sin borrar el contenido simulado en Redis.
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: None)
    semantic_cache.clear_semantic_cache()

    redis = RedisWithWeirdEntries()
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: redis)
    monkeypatch.setattr(semantic_cache, "_compute_embedding", lambda _q: [1.0, 0.0])
    monkeypatch.setattr(semantic_cache, "_compute_similarity", lambda *_a, **_k: 0.0)

    assert semantic_cache.get_semantic_cached_result("q") is None


def test_set_semantic_cache_noop_when_embedding_none(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")
    monkeypatch.setattr(semantic_cache, "_get_embedding_model", lambda: object())
    monkeypatch.setattr(semantic_cache, "_compute_embedding", lambda _q: None)
    semantic_cache.clear_semantic_cache()

    semantic_cache.set_semantic_cached_result("q", "r", "sql")
    assert semantic_cache._semantic_cache == {}


def test_clear_semantic_cache_redis_delete_failure(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")

    class BadRedis(FakeRedis):
        def delete(self, *keys):
            raise Exception("boom")

    bad = BadRedis()
    bad.store["semantic:x"] = (pickle.dumps({"expires_at": datetime.now() + timedelta(seconds=10)}), 10)
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: bad)
    monkeypatch.setattr(semantic_cache, "is_redis_enabled", lambda: True)

    semantic_cache._semantic_cache["a"] = {"expires_at": datetime.now() + timedelta(seconds=10)}
    semantic_cache._embedding_cache["e"] = [1.0]

    semantic_cache.clear_semantic_cache()  # no debe lanzar
    assert semantic_cache._semantic_cache == {}
    assert semantic_cache._embedding_cache == {}


def test_cleanup_expired_semantic_cache_redis_deletes_bad_and_expired(monkeypatch):
    class RedisForCleanup(FakeRedis):
        def __init__(self):
            super().__init__()
            now = datetime.now()
            # Missing data -> should be deleted
            self.store["semantic:missing"] = (None, 10)
            # Bad pickle -> should be deleted
            self.store["semantic:badpickle"] = (b"notpickle", 10)
            # Expired entry -> should be deleted
            self.store["semantic:expired"] = (pickle.dumps({"expires_at": now - timedelta(seconds=1)}), 10)
            # Active entry -> should remain
            self.store["semantic:active"] = (pickle.dumps({"expires_at": now + timedelta(seconds=60)}), 10)

    redis = RedisForCleanup()
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: redis)
    semantic_cache.cleanup_expired_semantic_cache()

    assert "semantic:active" in redis.store
    assert "semantic:missing" not in redis.store
    assert "semantic:badpickle" not in redis.store
    assert "semantic:expired" not in redis.store


def test_cleanup_expired_semantic_cache_redis_top_level_error(monkeypatch):
    class BadRedis:
        def scan_iter(self, *a, **k):
            raise Exception("boom")

    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: BadRedis())
    semantic_cache.cleanup_expired_semantic_cache()  # no debe lanzar


def test_initialize_semantic_cache_calls_preload(monkeypatch):
    called = {"ok": False}

    def fake_preload():
        called["ok"] = True
        return True

    monkeypatch.setattr(semantic_cache, "preload_embedding_model", fake_preload)
    semantic_cache.initialize_semantic_cache()
    assert called["ok"] is True


def test_get_semantic_cached_result_returns_none_when_question_embedding_missing(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")
    monkeypatch.setattr(semantic_cache, "get_redis_if_enabled", lambda: None)
    monkeypatch.setattr(semantic_cache, "_compute_embedding", lambda _q: None)
    assert semantic_cache.get_semantic_cached_result("q") is None
