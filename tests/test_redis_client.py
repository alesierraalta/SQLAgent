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
