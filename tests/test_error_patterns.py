"""Tests para Error Pattern Learning (Fase D)."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.utils.error_patterns import (
    ErrorPattern,
    ErrorPatternStore,
    get_error_pattern_store
)


@pytest.fixture
def temp_storage():
    """Crea un archivo temporal para almacenamiento de patrones."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def pattern_store(temp_storage):
    """Crea un ErrorPatternStore con almacenamiento temporal."""
    return ErrorPatternStore(storage_path=temp_storage)


def test_error_pattern_creation():
    """Verifica que se puede crear un ErrorPattern."""
    pattern = ErrorPattern(
        error_hash="abc123",
        original_sql="SELECT * FROM unknown_table",
        error_message="table 'unknown_table' does not exist",
        error_type="TABLE_NOT_FOUND",
        corrected_sql="SELECT * FROM sales"
    )
    
    assert pattern.error_hash == "abc123"
    assert pattern.success_count == 1
    assert pattern.first_seen != ""
    assert pattern.last_used != ""


def test_store_and_find_correction(pattern_store):
    """Verifica que se puede almacenar y encontrar una corrección."""
    original_sql = "SELECT revenue FROM sles"
    error_msg = "relation 'sles' does not exist"
    error_type = "TABLE_NOT_FOUND"
    corrected_sql = "SELECT revenue FROM sales"
    
    # Almacenar corrección
    pattern_store.store_successful_correction(
        original_sql=original_sql,
        error_message=error_msg,
        error_type=error_type,
        corrected_sql=corrected_sql
    )
    
    # Buscar corrección
    found = pattern_store.find_correction(
        original_sql=original_sql,
        error_message=error_msg,
        error_type=error_type
    )
    
    assert found == corrected_sql


def test_pattern_not_found(pattern_store):
    """Verifica que retorna None cuando no hay patrón conocido."""
    found = pattern_store.find_correction(
        original_sql="SELECT * FROM unknown",
        error_message="some error",
        error_type="UNKNOWN_ERROR"
    )
    
    assert found is None


def test_pattern_persistence(temp_storage):
    """Verifica que los patrones se persisten en disco."""
    # Crear store y agregar patrón
    store1 = ErrorPatternStore(storage_path=temp_storage)
    store1.store_successful_correction(
        original_sql="SELECT * FROM prodcts",
        error_message="relation 'prodcts' does not exist",
        error_type="TABLE_NOT_FOUND",
        corrected_sql="SELECT * FROM products"
    )
    
    # Crear nuevo store con mismo archivo
    store2 = ErrorPatternStore(storage_path=temp_storage)
    
    # Verificar que el patrón fue cargado
    found = store2.find_correction(
        original_sql="SELECT * FROM prodcts",
        error_message="relation 'prodcts' does not exist",
        error_type="TABLE_NOT_FOUND"
    )
    
    assert found == "SELECT * FROM products"


def test_success_count_increment(pattern_store):
    """Verifica que success_count se incrementa al reutilizar patrón."""
    original_sql = "SELECT * FROM sles"
    error_msg = "table 'sles' does not exist"
    error_type = "TABLE_NOT_FOUND"
    corrected_sql = "SELECT * FROM sales"
    
    # Almacenar primera vez
    pattern_store.store_successful_correction(
        original_sql=original_sql,
        error_message=error_msg,
        error_type=error_type,
        corrected_sql=corrected_sql
    )
    
    # Usar el patrón varias veces
    for _ in range(3):
        pattern_store.find_correction(
            original_sql=original_sql,
            error_message=error_msg,
            error_type=error_type
        )
    
    # Verificar que success_count aumentó
    error_hash = pattern_store._compute_error_hash(original_sql, error_msg)
    pattern = pattern_store.patterns[error_hash]
    assert pattern.success_count == 4  # 1 inicial + 3 usos


def test_error_hash_normalization(pattern_store):
    """Verifica que errores similares generan el mismo hash."""
    # Diferentes valores específicos pero mismo tipo de error
    sql1 = "SELECT * FROM table1"
    error1 = "column 'xyz' does not exist"
    
    sql2 = "SELECT * FROM table1"
    error2 = "column 'abc' does not exist"
    
    hash1 = pattern_store._compute_error_hash(sql1, error1)
    hash2 = pattern_store._compute_error_hash(sql2, error2)
    
    # Deberían generar el mismo hash (normalización de valores)
    assert hash1 == hash2


def test_get_statistics(pattern_store):
    """Verifica que se pueden obtener estadísticas."""
    # Agregar varios patrones
    for i in range(3):
        pattern_store.store_successful_correction(
            original_sql=f"SELECT * FROM table{i}",
            error_message=f"table 'table{i}' does not exist",
            error_type="TABLE_NOT_FOUND",
            corrected_sql=f"SELECT * FROM sales"
        )
    
    stats = pattern_store.get_statistics()
    
    assert stats["total_patterns"] == 3
    assert stats["total_uses"] == 3
    assert "TABLE_NOT_FOUND" in stats["error_types"]
    assert len(stats["most_common"]) <= 5


def test_clear_old_patterns(pattern_store):
    """Verifica que se pueden eliminar patrones antiguos."""
    from datetime import datetime, timedelta
    
    # Crear patrón antiguo manualmente
    old_date = (datetime.now() - timedelta(days=100)).isoformat()
    pattern = ErrorPattern(
        error_hash="old123",
        original_sql="SELECT * FROM old_table",
        error_message="table does not exist",
        error_type="TABLE_NOT_FOUND",
        corrected_sql="SELECT * FROM new_table",
        first_seen=old_date,
        last_used=old_date
    )
    pattern_store.patterns["old123"] = pattern
    pattern_store._save_patterns()
    
    # Limpiar patrones antiguos (>90 días)
    removed = pattern_store.clear_old_patterns(days=90)
    
    assert removed == 1
    assert "old123" not in pattern_store.patterns


def test_dont_store_identical_sql(pattern_store):
    """Verifica que no se almacena si SQL corregido es igual al original."""
    original_sql = "SELECT * FROM sales"
    
    pattern_store.store_successful_correction(
        original_sql=original_sql,
        error_message="some error",
        error_type="UNKNOWN_ERROR",
        corrected_sql=original_sql  # Mismo SQL
    )
    
    # No debería haberse almacenado
    assert len(pattern_store.patterns) == 0


def test_update_existing_pattern(pattern_store):
    """Verifica que se actualiza un patrón existente."""
    original_sql = "SELECT * FROM sles"
    error_msg = "table 'sles' does not exist"
    error_type = "TABLE_NOT_FOUND"
    
    # Primera corrección
    pattern_store.store_successful_correction(
        original_sql=original_sql,
        error_message=error_msg,
        error_type=error_type,
        corrected_sql="SELECT * FROM sales"
    )
    
    # Segunda corrección (mejor)
    pattern_store.store_successful_correction(
        original_sql=original_sql,
        error_message=error_msg,
        error_type=error_type,
        corrected_sql="SELECT * FROM sales LIMIT 100"
    )
    
    # Debería tener solo 1 patrón con la corrección más reciente
    assert len(pattern_store.patterns) == 1
    
    found = pattern_store.find_correction(
        original_sql=original_sql,
        error_message=error_msg,
        error_type=error_type
    )
    
    assert found == "SELECT * FROM sales LIMIT 100"


def test_singleton_store():
    """Verifica que get_error_pattern_store retorna singleton."""
    store1 = get_error_pattern_store()
    store2 = get_error_pattern_store()
    
    assert store1 is store2


def test_json_serialization(temp_storage):
    """Verifica que los patrones se serializan correctamente a JSON."""
    store = ErrorPatternStore(storage_path=temp_storage)
    
    store.store_successful_correction(
        original_sql="SELECT * FROM test",
        error_message="test error",
        error_type="TEST_ERROR",
        corrected_sql="SELECT * FROM test_corrected"
    )
    
    # Verificar que el archivo JSON es válido
    with open(temp_storage, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    assert isinstance(data, dict)
    assert len(data) == 1
    
    # Verificar estructura del patrón
    pattern_data = list(data.values())[0]
    assert "error_hash" in pattern_data
    assert "original_sql" in pattern_data
    assert "corrected_sql" in pattern_data
    assert "success_count" in pattern_data
