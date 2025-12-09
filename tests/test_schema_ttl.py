import os
"""Tests para Schema con TTL (Fase B)."""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.schemas.database_schema import (
    CachedSchema,
    DatabaseSchema,
    TableSchema,
    ColumnSchema,
    load_schema,
    invalidate_schema_cache,
    _schema_cache,
)


@pytest.fixture
def mock_schema():
    """Schema de prueba."""
    return DatabaseSchema(
        tables={
            "test_table": TableSchema(
                name="test_table",
                columns=[
                    ColumnSchema(name="id", type="INTEGER"),
                    ColumnSchema(name="name", type="VARCHAR"),
                ],
            ),
        }
    )


def test_cached_schema_not_expired():
    """Verifica que CachedSchema no expira antes del TTL."""
    schema = DatabaseSchema(tables={})
    cached = CachedSchema(
        schema=schema,
        fetched_at=datetime.now(),
        ttl_seconds=300
    )
    
    assert not cached.is_expired()


def test_cached_schema_expired():
    """Verifica que CachedSchema expira después del TTL."""
    schema = DatabaseSchema(tables={})
    # Simular que fue cacheado hace 10 minutos
    cached = CachedSchema(
        schema=schema,
        fetched_at=datetime.now() - timedelta(seconds=600),
        ttl_seconds=300  # 5 minutos
    )
    
    assert cached.is_expired()


def test_schema_cache_ttl_from_env(monkeypatch):
    """Verifica que el TTL se lee de variable de entorno."""
    # Limpiar cache
    invalidate_schema_cache()
    
    # Configurar TTL personalizado
    monkeypatch.setenv("SCHEMA_TTL_SECONDS", "60")
    monkeypatch.setenv("SCHEMA_DISCOVERY", "false")
    
    # Cargar schema
    schema = load_schema()
    
    # Verificar que el cache tiene el TTL correcto
    from src.schemas import database_schema
    assert database_schema._schema_cache is not None
    assert database_schema._schema_cache.ttl_seconds == 60


def test_schema_cache_reuse():
    """Verifica que el schema se reutiliza del cache."""
    # Limpiar cache
    invalidate_schema_cache()
    
    # Configurar para usar schema estático
    with patch.dict('os.environ', {'SCHEMA_DISCOVERY': 'false'}):
        # Primera carga
        schema1 = load_schema()
        
        # Segunda carga (debería usar cache)
        schema2 = load_schema()
        
        # Deberían ser el mismo objeto
        assert schema1 is schema2


def test_schema_cache_force_refresh():
    """Verifica que force_refresh ignora el cache."""
    # Limpiar cache
    invalidate_schema_cache()
    
    # Configurar para usar schema estático
    with patch.dict('os.environ', {'SCHEMA_DISCOVERY': 'false'}):
        # Primera carga
        schema1 = load_schema()
        
        # Segunda carga con force_refresh
        schema2 = load_schema(force_refresh=True)
        
        # Deberían ser objetos diferentes (nuevo schema cargado)
        assert schema1 is not schema2


def test_schema_cache_expiration():
    """Verifica que el cache expira y se recarga."""
    # Limpiar cache
    invalidate_schema_cache()
    
    # Configurar TTL muy corto
    with patch.dict('os.environ', {'SCHEMA_TTL_SECONDS': '1', 'SCHEMA_DISCOVERY': 'false'}):
        # Primera carga
        schema1 = load_schema()
        
        # Esperar a que expire
        time.sleep(1.5)
        
        # Segunda carga (debería recargar porque expiró)
        schema2 = load_schema()
        
        # Deberían ser objetos diferentes
        assert schema1 is not schema2


def test_invalidate_schema_cache():
    """Verifica que invalidate_schema_cache limpia el cache."""
    # Limpiar cache
    invalidate_schema_cache()
    
    # Configurar para usar schema estático
    with patch.dict('os.environ', {'SCHEMA_DISCOVERY': 'false'}):
        # Cargar schema
        load_schema()
        
        # Verificar que hay cache
        from src.schemas import database_schema
        assert database_schema._schema_cache is not None
        
        # Invalidar
        invalidate_schema_cache()
        
        # Verificar que el cache fue limpiado
        assert database_schema._schema_cache is None


def test_schema_cache_default_ttl():
    """Verifica que el TTL por defecto es 300 segundos."""
    # Limpiar cache
    invalidate_schema_cache()
    
    # Cargar sin configurar TTL
    with patch.dict('os.environ', {'SCHEMA_DISCOVERY': 'false'}, clear=True):
        # Asegurar que SCHEMA_TTL_SECONDS no está definido
        if 'SCHEMA_TTL_SECONDS' in os.environ:
            del os.environ['SCHEMA_TTL_SECONDS']
        
        load_schema()
        
        # Verificar TTL por defecto
        from src.schemas import database_schema
        assert database_schema._schema_cache.ttl_seconds == 300


def test_schema_cache_with_discovery_disabled():
    """Verifica que el cache funciona con discovery deshabilitado."""
    # Limpiar cache
    invalidate_schema_cache()
    
    with patch.dict('os.environ', {'SCHEMA_DISCOVERY': 'false', 'SCHEMA_TTL_SECONDS': '60'}):
        # Primera carga
        schema1 = load_schema()
        assert len(schema1.tables) > 0
        
        # Segunda carga (desde cache)
        schema2 = load_schema()
        assert schema1 is schema2

