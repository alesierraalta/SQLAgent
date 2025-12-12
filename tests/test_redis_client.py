import sys
from types import SimpleNamespace

import pytest

from src.utils import redis_client


def test_get_redis_client_import_error(monkeypatch):
    # Simular que redis no está instalado
    redis_client.get_redis_client.cache_clear()
    monkeypatch.setitem(sys.modules, "redis", None)
    client = redis_client.get_redis_client()
    assert client is None


def test_get_redis_client_connection_failure(monkeypatch):
    redis_client.get_redis_client.cache_clear()
    mock_redis = SimpleNamespace(from_url=lambda *a, **k: SimpleNamespace(ping=lambda: (_ for _ in ()).throw(Exception("fail"))))
    monkeypatch.setitem(sys.modules, "redis", mock_redis)
    client = redis_client.get_redis_client()
    assert client is None


def test_get_redis_client_success(monkeypatch):
    redis_client.get_redis_client.cache_clear()
    class Dummy:
        def __init__(self):
            self.pings = 0

        def ping(self):
            self.pings += 1

    dummy = Dummy()

    class DummyRedis:
        def from_url(self, *args, **kwargs):
            return dummy

    monkeypatch.setitem(sys.modules, "redis", DummyRedis())
    client = redis_client.get_redis_client()
    assert client is dummy
    assert dummy.pings == 1


def test_acquire_release_lock(monkeypatch):
    calls = {"set": 0, "delete": 0}

    class FakeClient:
        def set(self, name, value, nx, ex):
            calls["set"] += 1
            return True

        def delete(self, key):
            calls["delete"] += 1

    monkeypatch.setattr(redis_client, "get_redis_if_enabled", lambda: FakeClient())

    assert redis_client.acquire_lock("k", ttl_seconds=1) is True
    redis_client.release_lock("k")
    assert calls["set"] == 1
    assert calls["delete"] == 1


def test_acquire_lock_fallback_when_no_redis(monkeypatch):
    monkeypatch.setattr(redis_client, "get_redis_if_enabled", lambda: None)
    assert redis_client.acquire_lock("k") is True


def test_acquire_lock_handles_set_exception(monkeypatch):
    class BadClient:
        def set(self, *a, **k):
            raise Exception("boom")

    monkeypatch.setattr(redis_client, "get_redis_if_enabled", lambda: BadClient())
    assert redis_client.acquire_lock("k") is True


def test_get_redis_client_returns_none_when_url_empty(monkeypatch):
    redis_client.get_redis_client.cache_clear()
    # Forzar URL vacía para cubrir rama
    monkeypatch.setattr(redis_client, "_build_redis_url", lambda: "")
    monkeypatch.setitem(sys.modules, "redis", SimpleNamespace(from_url=lambda *a, **k: SimpleNamespace(ping=lambda: None)))
    assert redis_client.get_redis_client() is None


def test_get_redis_if_enabled_respects_flag(monkeypatch):
    monkeypatch.setenv("USE_REDIS_CACHE", "false")
    assert redis_client.get_redis_if_enabled() is None


def test_release_lock_noop_when_no_client(monkeypatch):
    monkeypatch.setattr(redis_client, "get_redis_if_enabled", lambda: None)
    redis_client.release_lock("k")  # no debe lanzar


def test_release_lock_handles_delete_exception(monkeypatch):
    class BadClient:
        def delete(self, key):
            raise Exception("boom")

    monkeypatch.setattr(redis_client, "get_redis_if_enabled", lambda: BadClient())
    redis_client.release_lock("k")  # no debe lanzar


def test_build_redis_url_from_parts(monkeypatch):
    """Cubre construcción de URL cuando no hay REDIS_URL."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("REDIS_HOST", "host")
    monkeypatch.setenv("REDIS_PORT", "1234")
    monkeypatch.setenv("REDIS_DB", "2")
    monkeypatch.setenv("REDIS_PASSWORD", "pw")

    url = redis_client._build_redis_url()
    assert "pw@" in url
    assert "host:1234/2" in url
