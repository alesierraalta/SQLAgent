"""Tests para cache SQL (src/utils/cache.py)."""

from datetime import datetime, timedelta

import pytest

from src.utils import cache
from src.utils.persistent_cache import MemoryCache


def test_normalize_sql_empty_parse(monkeypatch):
    monkeypatch.setattr(cache.sqlparse, "parse", lambda sql: [])
    assert cache.normalize_sql("select 1") == "SELECT 1"


def test_normalize_sql_fallback_on_exception(monkeypatch):
    def _raise(*args, **kwargs):
        raise Exception("boom")

    monkeypatch.setattr(cache.sqlparse, "parse", _raise)
    assert cache.normalize_sql("select 1") == "SELECT 1"


def test_set_and_get_cached_result(monkeypatch):
    backend = MemoryCache()
    monkeypatch.setattr(cache, "_cache_backend", backend)

    cache.set_cached_result("SELECT 1", "res", ttl_seconds=60)
    assert cache.get_cached_result("SELECT 1") == "res"


def test_get_cached_result_returns_none_when_missing(monkeypatch):
    backend = MemoryCache()
    monkeypatch.setattr(cache, "_cache_backend", backend)
    assert cache.get_cached_result("SELECT 1") is None


def test_get_cached_result_expired_entry_is_deleted(monkeypatch):
    backend = MemoryCache()
    monkeypatch.setattr(cache, "_cache_backend", backend)

    sql = "SELECT 1"
    sql_hash = cache.get_sql_hash(sql)
    backend.set(
        sql_hash,
        {
            "result": "old",
            "expires_at": datetime.now() - timedelta(seconds=1),
            "cached_at": datetime.now(),
            "sql_preview": sql,
        },
    )

    assert cache.get_cached_result(sql) is None
    assert backend.get(sql_hash) is None


def test_invalidate_cache_none_clears_all(monkeypatch):
    backend = MemoryCache()
    backend.set("k", {"result": "x", "expires_at": datetime.now() + timedelta(seconds=10), "cached_at": datetime.now(), "sql_preview": ""})
    monkeypatch.setattr(cache, "_cache_backend", backend)

    cache.invalidate_cache()
    assert backend.get_stats()["total_entries"] == 0


def test_cleanup_expired_cache_calls_backend_when_supported(monkeypatch):
    class DummyBackend(MemoryCache):
        def cleanup_expired(self):
            return 2

    backend = DummyBackend()
    monkeypatch.setattr(cache, "_cache_backend", backend)

    cache.cleanup_expired_cache()  # no debe lanzar


def test_get_cache_uses_memory_when_redis_disabled(monkeypatch):
    """Cubre rama _get_cache cuando CACHE_BACKEND=redis pero USE_REDIS_CACHE=false."""
    monkeypatch.setattr(cache, "_cache_backend", None)
    monkeypatch.setenv("USE_REDIS_CACHE", "false")
    monkeypatch.setenv("CACHE_BACKEND", "redis")

    backend = cache._get_cache()
    assert isinstance(backend, MemoryCache)


def test_get_cache_uses_backend_factory_when_not_forced_memory(monkeypatch):
    """Cubre rama _get_cache que llama a get_cache_backend()."""
    sentinel = MemoryCache()
    monkeypatch.setattr(cache, "_cache_backend", None)
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    monkeypatch.setenv("USE_REDIS_CACHE", "true")
    monkeypatch.setattr(cache, "get_cache_backend", lambda: sentinel)

    backend = cache._get_cache()
    assert backend is sentinel


def test_invalidate_cache_specific_sql(monkeypatch):
    backend = MemoryCache()
    monkeypatch.setattr(cache, "_cache_backend", backend)

    cache.set_cached_result("SELECT 1", "res", ttl_seconds=60)
    cache.invalidate_cache("SELECT 1")
    assert backend.get_stats()["total_entries"] == 0


def test_get_cache_stats_includes_ttl_seconds(monkeypatch):
    backend = MemoryCache()
    monkeypatch.setattr(cache, "_cache_backend", backend)

    stats = cache.get_cache_stats()
    assert "ttl_seconds" in stats


def test_cleanup_expired_cache_when_backend_has_no_cleanup(monkeypatch):
    """Cubre rama else de cleanup_expired_cache."""
    backend = MemoryCache()
    monkeypatch.setattr(cache, "_cache_backend", backend)
    cache.cleanup_expired_cache()
