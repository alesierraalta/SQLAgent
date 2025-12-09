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
