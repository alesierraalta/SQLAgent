"""Tests para utilidades de base de datos."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.utils.database import (
    get_db_connection,
    get_db_engine,
    dispose_engine,
    test_connection as db_test_connection,
)
from src.utils.exceptions import DatabaseConnectionError


def test_import_database_module():
    """Asegura que el módulo database se importe (cobertura)."""
    import importlib

    module = importlib.import_module("src.utils.database")
    assert module is not None


@patch("src.utils.database.create_engine")
@patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db", "QUERY_TIMEOUT": "30"})
def test_get_db_engine_success(mock_create_engine):
    """Test: Obtención exitosa del engine."""
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    engine = get_db_engine()

    assert engine == mock_engine
    mock_create_engine.assert_called_once()
    kwargs = mock_create_engine.call_args.kwargs
    assert "-c statement_timeout=30000" in kwargs["connect_args"]["options"]
    assert "default_transaction_read_only=on" in kwargs["connect_args"]["options"]


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


@patch("src.utils.database.create_engine")
@patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"})
def test_get_db_engine_connection_error(mock_create_engine):
    """Test: Error al crear engine propaga DatabaseConnectionError."""
    mock_create_engine.side_effect = Exception("bad url")
    with pytest.raises(DatabaseConnectionError):
        get_db_engine()


@patch("src.utils.database.create_engine")
@patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"})
def test_get_db_engine_uses_cache_for_same_url(mock_create_engine):
    """Test: segundo get_db_engine con misma URL reusa engine."""
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    engine1 = get_db_engine()
    engine2 = get_db_engine()

    assert engine1 is engine2
    mock_create_engine.assert_called_once()


def test_sanitize_url_without_credentials_returns_masked():
    """Test: _sanitize_url retorna '***' si no hay credenciales."""
    from src.utils import database

    assert database._sanitize_url("postgresql://localhost/db") == "***"
    assert database._sanitize_url(None) == "***"


def test_get_db_connection_retries_then_succeeds(monkeypatch):
    """Test: get_db_connection reintenta y luego retorna conexión."""
    engine = MagicMock()
    mock_conn = MagicMock()
    success_cm = MagicMock()
    success_cm.__enter__.return_value = mock_conn
    success_cm.__exit__.return_value = False

    engine.connect.side_effect = [Exception("fail"), success_cm]
    monkeypatch.setattr("src.utils.database.get_db_engine", lambda: engine)
    monkeypatch.setattr("src.utils.database.time.sleep", lambda *_: None)

    with get_db_connection() as conn:
        assert conn is mock_conn


def test_get_db_connection_raises_after_retries(monkeypatch):
    """Test: get_db_connection lanza DatabaseConnectionError tras agotar intentos."""
    engine = MagicMock()
    engine.url = "postgresql://user:pass@localhost/db"
    engine.connect.side_effect = Exception("fail")

    monkeypatch.setattr("src.utils.database.get_db_engine", lambda: engine)
    monkeypatch.setattr("src.utils.database.time.sleep", lambda *_: None)

    with pytest.raises(DatabaseConnectionError):
        with get_db_connection():
            pass


def test_dispose_engine_disposes_when_present(monkeypatch):
    """Test: dispose_engine llama dispose y limpia el singleton."""
    from src.utils import database

    mock_engine = MagicMock()
    monkeypatch.setattr(database, "_engine", mock_engine)

    dispose_engine()

    mock_engine.dispose.assert_called_once()
    assert database._engine is None
