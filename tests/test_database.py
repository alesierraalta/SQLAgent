"""Tests para utilidades de base de datos."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.utils.database import get_db_engine, test_connection as db_test_connection
from src.utils.exceptions import DatabaseConnectionError


def test_import_database_module():
    """Asegura que el módulo database se importe (cobertura)."""
    import importlib

    module = importlib.import_module("src.utils.database")
    assert module is not None


@patch("src.utils.database.create_engine")
@patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"})
def test_get_db_engine_success(mock_create_engine):
    """Test: Obtención exitosa del engine."""
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    engine = get_db_engine()

    assert engine == mock_engine
    mock_create_engine.assert_called_once()


@patch.dict(os.environ, {}, clear=True)
def test_get_db_engine_no_url():
    """Test: Error cuando no hay DATABASE_URL."""
    with pytest.raises(DatabaseConnectionError):
        get_db_engine()


@patch("src.utils.database.get_db_engine")
def test_test_connection_success(mock_get_engine):
    """Test: Conexión exitosa."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value = None
    mock_get_engine.return_value = mock_engine

    result = db_test_connection()

    assert result is True


@patch("src.utils.database.get_db_engine")
def test_test_connection_failure(mock_get_engine):
    """Test: Conexión fallida."""
    mock_get_engine.side_effect = Exception("Connection error")

    result = db_test_connection()

    assert result is False
