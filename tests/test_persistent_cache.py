"""Tests para Cache Persistente (Fase C)."""

import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.persistent_cache import (
    CacheBackend,
    MemoryCache,
    FileCache,
    get_cache_backend
)


@pytest.fixture
def temp_cache_dir():
    """Crea un directorio temporal para cache de archivos."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def memory_cache():
    """Crea un MemoryCache."""
    return MemoryCache()


@pytest.fixture
def file_cache(temp_cache_dir):
    """Crea un FileCache con directorio temporal."""
    return FileCache(cache_dir=temp_cache_dir)


def test_memory_cache_set_and_get(memory_cache):
    """Verifica que MemoryCache puede guardar y recuperar valores."""
    key = "test_key"
    value = {
        'result': "test result",
        'expires_at': datetime.now() + timedelta(hours=1),
        'cached_at': datetime.now(),
        'sql_preview': "SELECT * FROM test"
    }
    
    memory_cache.set(key, value)
    retrieved = memory_cache.get(key)
    
    assert retrieved is not None
    assert retrieved['result'] == "test result"


def test_memory_cache_expiration(memory_cache):
    """Verifica que MemoryCache respeta expiración."""
    key = "test_key"
    value = {
        'result': "test result",
        'expires_at': datetime.now() - timedelta(seconds=1),  # Expirado
        'cached_at': datetime.now(),
        'sql_preview': "SELECT * FROM test"
    }
    
    memory_cache.set(key, value)
    retrieved = memory_cache.get(key)
    
    # Debería retornar el valor (MemoryCache no valida expiración, eso lo hace cache.py)
    assert retrieved is not None


def test_memory_cache_delete(memory_cache):
    """Verifica que MemoryCache puede eliminar entradas."""
    key = "test_key"
    value = {
        'result': "test result",
        'expires_at': datetime.now() + timedelta(hours=1),
        'cached_at': datetime.now(),
        'sql_preview': "SELECT * FROM test"
    }
    
    memory_cache.set(key, value)
    assert memory_cache.get(key) is not None
    
    memory_cache.delete(key)
    assert memory_cache.get(key) is None


def test_memory_cache_clear(memory_cache):
    """Verifica que MemoryCache puede limpiar todo el cache."""
    for i in range(5):
        key = f"key_{i}"
        value = {
            'result': f"result_{i}",
            'expires_at': datetime.now() + timedelta(hours=1),
            'cached_at': datetime.now(),
            'sql_preview': f"SELECT {i}"
        }
        memory_cache.set(key, value)
    
    stats = memory_cache.get_stats()
    assert stats['total_entries'] == 5
    
    memory_cache.clear()
    stats = memory_cache.get_stats()
    assert stats['total_entries'] == 0


def test_memory_cache_stats(memory_cache):
    """Verifica que MemoryCache retorna estadísticas correctas."""
    # Agregar entradas activas
    for i in range(3):
        key = f"active_{i}"
        value = {
            'result': f"result_{i}",
            'expires_at': datetime.now() + timedelta(hours=1),
            'cached_at': datetime.now(),
            'sql_preview': f"SELECT {i}"
        }
        memory_cache.set(key, value)
    
    # Agregar entradas expiradas
    for i in range(2):
        key = f"expired_{i}"
        value = {
            'result': f"result_{i}",
            'expires_at': datetime.now() - timedelta(hours=1),
            'cached_at': datetime.now(),
            'sql_preview': f"SELECT {i}"
        }
        memory_cache.set(key, value)
    
    stats = memory_cache.get_stats()
    assert stats['backend'] == 'memory'
    assert stats['total_entries'] == 5
    assert stats['active_entries'] == 3
    assert stats['expired_entries'] == 2


def test_file_cache_set_and_get(file_cache):
    """Verifica que FileCache puede guardar y recuperar valores."""
    key = "test_key"
    value = {
        'result': "test result",
        'expires_at': datetime.now() + timedelta(hours=1),
        'cached_at': datetime.now(),
        'sql_preview': "SELECT * FROM test"
    }
    
    file_cache.set(key, value)
    retrieved = file_cache.get(key)
    
    assert retrieved is not None
    assert retrieved['result'] == "test result"


def test_file_cache_persistence(temp_cache_dir):
    """Verifica que FileCache persiste entre instancias."""
    key = "test_key"
    value = {
        'result': "test result",
        'expires_at': datetime.now() + timedelta(hours=1),
        'cached_at': datetime.now(),
        'sql_preview': "SELECT * FROM test"
    }
    
    # Primera instancia: guardar
    cache1 = FileCache(cache_dir=temp_cache_dir)
    cache1.set(key, value)
    
    # Segunda instancia: recuperar
    cache2 = FileCache(cache_dir=temp_cache_dir)
    retrieved = cache2.get(key)
    
    assert retrieved is not None
    assert retrieved['result'] == "test result"


def test_file_cache_expiration(file_cache):
    """Verifica que FileCache elimina entradas expiradas."""
    key = "test_key"
    value = {
        'result': "test result",
        'expires_at': datetime.now() - timedelta(seconds=1),  # Expirado
        'cached_at': datetime.now(),
        'sql_preview': "SELECT * FROM test"
    }
    
    file_cache.set(key, value)
    
    # get() debería retornar None y eliminar la entrada
    retrieved = file_cache.get(key)
    assert retrieved is None
    
    # Verificar que fue eliminado
    assert key not in file_cache._index


def test_file_cache_cleanup_expired(file_cache):
    """Verifica que FileCache puede limpiar entradas expiradas."""
    # Agregar entradas activas
    for i in range(3):
        key = f"active_{i}"
        value = {
            'result': f"result_{i}",
            'expires_at': datetime.now() + timedelta(hours=1),
            'cached_at': datetime.now(),
            'sql_preview': f"SELECT {i}"
        }
        file_cache.set(key, value)
    
    # Agregar entradas expiradas
    for i in range(2):
        key = f"expired_{i}"
        value = {
            'result': f"result_{i}",
            'expires_at': datetime.now() - timedelta(hours=1),
            'cached_at': datetime.now(),
            'sql_preview': f"SELECT {i}"
        }
        file_cache.set(key, value)
    
    # Limpiar expirados
    removed = file_cache.cleanup_expired()
    
    assert removed == 2
    assert len(file_cache._index) == 3


def test_file_cache_stats(file_cache):
    """Verifica que FileCache retorna estadísticas correctas."""
    # Agregar algunas entradas
    for i in range(3):
        key = f"key_{i}"
        value = {
            'result': f"result_{i}",
            'expires_at': datetime.now() + timedelta(hours=1),
            'cached_at': datetime.now(),
            'sql_preview': f"SELECT {i}"
        }
        file_cache.set(key, value)
    
    stats = file_cache.get_stats()
    
    assert stats['backend'] == 'file'
    assert stats['total_entries'] == 3
    assert stats['active_entries'] == 3
    assert 'total_size_bytes' in stats
    assert 'cache_dir' in stats


def test_file_cache_subdirectories(file_cache):
    """Verifica que FileCache crea subdirectorios correctamente."""
    key = "abcdef123456"
    value = {
        'result': "test",
        'expires_at': datetime.now() + timedelta(hours=1),
        'cached_at': datetime.now(),
        'sql_preview': "SELECT"
    }
    
    file_cache.set(key, value)
    
    # Verificar que se creó subdirectorio con primeros 2 caracteres
    cache_file = file_cache._get_cache_file(key)
    assert cache_file.parent.name == "ab"
    assert cache_file.exists()


def test_get_cache_backend_memory():
    """Verifica que get_cache_backend retorna MemoryCache por defecto."""
    with patch.dict('os.environ', {'CACHE_BACKEND': 'memory'}):
        backend = get_cache_backend()
        assert isinstance(backend, MemoryCache)


def test_get_cache_backend_file():
    """Verifica que get_cache_backend retorna FileCache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict('os.environ', {'CACHE_BACKEND': 'file', 'CACHE_DIR': tmpdir}):
            backend = get_cache_backend()
            assert isinstance(backend, FileCache)


def test_get_cache_backend_invalid():
    """Verifica que get_cache_backend usa memory para backend inválido."""
    with patch.dict('os.environ', {'CACHE_BACKEND': 'invalid'}):
        backend = get_cache_backend()
        assert isinstance(backend, MemoryCache)


def test_cache_backend_interface(temp_cache_dir):
    """Verifica que todos los backends implementan la interfaz correctamente."""
    backends = [
        MemoryCache(),
        FileCache(cache_dir=temp_cache_dir),
    ]

    for backend in backends:
        # Verificar que tiene todos los métodos requeridos
        assert hasattr(backend, 'get')
        assert hasattr(backend, 'set')
        assert hasattr(backend, 'delete')
        assert hasattr(backend, 'clear')
        assert hasattr(backend, 'get_stats')
        
        # Verificar que los métodos funcionan
        key = "test"
        value = {
            'result': "test",
            'expires_at': datetime.now() + timedelta(hours=1),
            'cached_at': datetime.now(),
            'sql_preview': "SELECT"
        }
        
        backend.set(key, value)
        assert backend.get(key) is not None
        
        backend.delete(key)
        assert backend.get(key) is None
        
        stats = backend.get_stats()
        assert 'backend' in stats
        assert 'total_entries' in stats


def test_file_cache_load_index_invalid_json(temp_cache_dir):
    """Cubre excepción al cargar index.json corrupto."""
    from pathlib import Path
    from src.utils.persistent_cache import FileCache

    index_file = Path(temp_cache_dir) / "index.json"
    index_file.write_text("{bad json", encoding="utf-8")

    cache = FileCache(cache_dir=temp_cache_dir)
    assert cache._index == {}


def test_file_cache_save_index_handles_error(file_cache, monkeypatch):
    """Cubre excepción al guardar index.json."""

    def _raise(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr("builtins.open", _raise)
    file_cache._index["k"] = "v"
    file_cache._save_index()  # no debe lanzar


def test_file_cache_get_missing_file_cleans_index(file_cache):
    """Cubre rama donde index apunta a archivo inexistente."""
    key = "ab_missing"
    cache_file = file_cache._get_cache_file(key)
    file_cache._index[key] = str(cache_file)

    assert file_cache.get(key) is None
    assert key not in file_cache._index


def test_file_cache_get_handles_unpickle_error(file_cache):
    """Cubre excepción al leer pickle corrupto."""
    key = "ab_corrupt"
    cache_file = file_cache._get_cache_file(key)
    cache_file.write_bytes(b"not a pickle")
    file_cache._index[key] = str(cache_file)

    assert file_cache.get(key) is None


def test_file_cache_set_handles_write_error(file_cache, monkeypatch):
    """Cubre excepción al escribir archivo de cache."""

    def _raise(*args, **kwargs):
        raise OSError("write fail")

    monkeypatch.setattr("builtins.open", _raise)
    file_cache.set("ab_key", {"result": "x", "expires_at": datetime.now(), "cached_at": datetime.now(), "sql_preview": ""})


def test_get_cache_backend_redis_falls_back_to_file(monkeypatch):
    """Cubre fallback a FileCache cuando RedisCache no está disponible."""
    from src.utils import persistent_cache

    monkeypatch.setenv("CACHE_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    def _raise(*args, **kwargs):
        raise ImportError("no redis")

    monkeypatch.setattr(persistent_cache, "RedisCache", _raise)

    backend = persistent_cache.get_cache_backend()
    assert isinstance(backend, persistent_cache.FileCache)


def test_redis_cache_basic_operations(monkeypatch):
    """Cubre RedisCache usando módulo redis fake."""
    from src.utils.persistent_cache import RedisCache

    class FakeClient:
        def __init__(self):
            self.store = {}

        def ping(self):
            return True

        def get(self, key):
            return self.store.get(key)

        def setex(self, key, ttl, data):
            self.store[key] = data

        def delete(self, key):
            self.store.pop(key, None)

        def flushdb(self):
            self.store.clear()

        def info(self, section):
            return {"keyspace_hits": 1, "keyspace_misses": 2}

        def dbsize(self):
            return len(self.store)

    fake_client = FakeClient()

    class FakeRedis:
        def from_url(self, *a, **k):
            return fake_client

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())

    rc = RedisCache(redis_url="redis://test")
    key = "k1"
    value = {
        "result": "x",
        "expires_at": datetime.now() + timedelta(seconds=60),
        "cached_at": datetime.now(),
        "sql_preview": "SELECT 1",
    }
    rc.set(key, value)
    assert rc.get(key)["result"] == "x"

    stats = rc.get_stats()
    assert stats["backend"] == "redis"
    rc.clear()
    assert fake_client.store == {}


def test_file_cache_delete_missing_key_is_noop(file_cache):
    file_cache.delete("ab_missing")  # no debe lanzar


def test_file_cache_delete_handles_unlink_error(file_cache, monkeypatch):
    key = "ab_err"
    value = {
        "result": "x",
        "expires_at": datetime.now() + timedelta(seconds=60),
        "cached_at": datetime.now(),
        "sql_preview": "SELECT 1",
    }
    file_cache.set(key, value)

    def boom(self, missing_ok: bool = False):
        raise OSError("boom")

    monkeypatch.setattr(Path, "unlink", boom)
    file_cache.delete(key)  # no debe lanzar


def test_file_cache_clear_removes_entries(file_cache):
    for i in range(2):
        file_cache.set(
            f"ab_{i}",
            {
                "result": f"r{i}",
                "expires_at": datetime.now() + timedelta(seconds=60),
                "cached_at": datetime.now(),
                "sql_preview": "SELECT 1",
            },
        )

    assert file_cache._index
    file_cache.clear()
    assert file_cache._index == {}


def test_file_cache_clear_handles_exception(file_cache, monkeypatch):
    file_cache._index["ab"] = "x"

    def boom(_key: str):
        raise Exception("boom")

    monkeypatch.setattr(file_cache, "delete", boom)
    file_cache.clear()  # no debe lanzar


def test_file_cache_get_stats_skips_missing_file(file_cache):
    key = "ab_missingstat"
    file_cache._index[key] = str(file_cache._get_cache_file(key))
    stats = file_cache.get_stats()
    assert stats["backend"] == "file"


def test_file_cache_get_stats_counts_expired_and_ignores_bad_pickle(file_cache):
    expired_key = "ab_expired"
    file_cache.set(
        expired_key,
        {
            "result": "old",
            "expires_at": datetime.now() - timedelta(seconds=1),
            "cached_at": datetime.now(),
            "sql_preview": "SELECT 1",
        },
    )

    bad_key = "ab_badstats"
    bad_file = file_cache._get_cache_file(bad_key)
    bad_file.write_bytes(b"not a pickle")
    file_cache._index[bad_key] = str(bad_file)

    stats = file_cache.get_stats()
    assert stats["expired_entries"] >= 1


def test_redis_cache_init_raises_import_error_when_module_missing(monkeypatch):
    from src.utils.persistent_cache import RedisCache

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(ImportError):
        RedisCache(redis_url="redis://test")


def test_redis_cache_uses_env_url_when_none(monkeypatch):
    from src.utils.persistent_cache import RedisCache

    class FakeClient:
        def ping(self):
            return True

        def get(self, key):
            return None

        def setex(self, key, ttl, data):
            return None

        def delete(self, key):
            return None

        def flushdb(self):
            return None

        def info(self, section):
            return {}

        def dbsize(self):
            return 0

    client = FakeClient()

    class FakeRedis:
        def from_url(self, *a, **k):
            return client

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())
    monkeypatch.setenv("REDIS_URL", "redis://env")

    rc = RedisCache(redis_url=None)
    assert rc.redis_url == "redis://env"


def test_redis_cache_init_raises_connection_error_when_ping_fails(monkeypatch):
    from src.utils.persistent_cache import RedisCache

    class BadClient:
        def ping(self):
            raise Exception("boom")

    class FakeRedis:
        def from_url(self, *a, **k):
            return BadClient()

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())

    with pytest.raises(ConnectionError):
        RedisCache(redis_url="redis://test")


def test_redis_cache_get_returns_none_when_missing_key(monkeypatch):
    from src.utils.persistent_cache import RedisCache

    class FakeClient:
        def ping(self):
            return True

        def get(self, key):
            return None

    class FakeRedis:
        def from_url(self, *a, **k):
            return FakeClient()

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())
    rc = RedisCache(redis_url="redis://test")
    assert rc.get("missing") is None


def test_redis_cache_get_deletes_when_expired(monkeypatch):
    import pickle
    from src.utils.persistent_cache import RedisCache

    class FakeClient:
        def __init__(self):
            self.store = {}

        def ping(self):
            return True

        def get(self, key):
            return self.store.get(key)

        def delete(self, key):
            self.store.pop(key, None)

    client = FakeClient()

    class FakeRedis:
        def from_url(self, *a, **k):
            return client

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())
    rc = RedisCache(redis_url="redis://test")

    key = "k"
    client.store[key] = pickle.dumps(
        {
            "result": "x",
            "expires_at": datetime.now() - timedelta(seconds=1),
            "cached_at": datetime.now(),
            "sql_preview": "SELECT 1",
        }
    )

    assert rc.get(key) is None
    assert key not in client.store


def test_redis_cache_get_handles_exception(monkeypatch):
    from src.utils.persistent_cache import RedisCache

    class BadClient:
        def ping(self):
            return True

        def get(self, key):
            raise Exception("boom")

    class FakeRedis:
        def from_url(self, *a, **k):
            return BadClient()

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())
    rc = RedisCache(redis_url="redis://test")
    assert rc.get("k") is None


def test_redis_cache_set_handles_exception(monkeypatch):
    from src.utils.persistent_cache import RedisCache

    class BadClient:
        def ping(self):
            return True

        def setex(self, *a, **k):
            raise Exception("boom")

    class FakeRedis:
        def from_url(self, *a, **k):
            return BadClient()

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())
    rc = RedisCache(redis_url="redis://test")
    rc.set(
        "k",
        {
            "result": "x",
            "expires_at": datetime.now() + timedelta(seconds=60),
            "cached_at": datetime.now(),
            "sql_preview": "SELECT 1",
        },
    )


def test_redis_cache_delete_handles_exception(monkeypatch):
    from src.utils.persistent_cache import RedisCache

    class BadClient:
        def ping(self):
            return True

        def delete(self, key):
            raise Exception("boom")

    class FakeRedis:
        def from_url(self, *a, **k):
            return BadClient()

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())
    rc = RedisCache(redis_url="redis://test")
    rc.delete("k")  # no debe lanzar


def test_redis_cache_clear_handles_exception(monkeypatch):
    from src.utils.persistent_cache import RedisCache

    class BadClient:
        def ping(self):
            return True

        def flushdb(self):
            raise Exception("boom")

    class FakeRedis:
        def from_url(self, *a, **k):
            return BadClient()

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())
    rc = RedisCache(redis_url="redis://test")
    rc.clear()  # no debe lanzar


def test_redis_cache_get_stats_handles_exception(monkeypatch):
    from src.utils.persistent_cache import RedisCache

    class BadClient:
        def ping(self):
            return True

        def info(self, section):
            raise Exception("boom")

        def dbsize(self):
            return 0

    class FakeRedis:
        def from_url(self, *a, **k):
            return BadClient()

    monkeypatch.setitem(os.sys.modules, "redis", FakeRedis())
    rc = RedisCache(redis_url="redis://test")
    stats = rc.get_stats()
    assert stats["backend"] == "redis"
    assert "error" in stats
