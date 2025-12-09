"""Tests para el CLI."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import cli


@pytest.fixture
def runner():
    """Fixture para CliRunner."""
    return CliRunner()


@patch("src.cli.load_schema")
@patch("src.cli.get_db_engine")
@patch("src.cli.create_sql_agent")
@patch("src.cli.execute_query")
def test_query_command(mock_execute, mock_create_agent, mock_engine, mock_schema, runner, sample_schema):
    """Test: Comando query."""
    # Configurar mocks
    mock_schema.return_value = sample_schema
    mock_engine.return_value = MagicMock()
    mock_agent = MagicMock()
    mock_create_agent.return_value = mock_agent
    mock_execute.return_value = "Respuesta de prueba"

    # Ejecutar comando
    result = runner.invoke(cli, ["query", "¿Cuál es el total?"])

    # Verificar
    assert result.exit_code == 0
    assert "Respuesta de prueba" in result.output


@patch("src.cli.load_schema")
def test_schema_command(mock_schema, runner, sample_schema):
    """Test: Comando schema."""
    mock_schema.return_value = sample_schema

    result = runner.invoke(cli, ["schema"])

    assert result.exit_code == 0
    assert "sales" in result.output or "products" in result.output


@patch("src.cli.test_connection")
def test_test_connection_success(mock_test, runner):
    """Test: Comando test-connection exitoso."""
    mock_test.return_value = True

    result = runner.invoke(cli, ["test-connection"])

    assert result.exit_code == 0
    assert "Conexión exitosa" in result.output or "exitosa" in result.output.lower()


@patch("src.cli.test_connection")
def test_test_connection_failure(mock_test, runner):
    """Test: Comando test-connection fallido."""
    mock_test.return_value = False

    result = runner.invoke(cli, ["test-connection"])

    assert result.exit_code == 1
    assert "Error" in result.output or "fallo" in result.output.lower()


@patch("src.cli.load_schema")
@patch("src.cli.SQLValidator")
def test_validate_sql_command_valid(mock_validator_class, mock_schema, runner, sample_schema):
    """Test: Comando validate-sql con SQL válido."""
    mock_schema.return_value = sample_schema
    mock_validator = MagicMock()
    mock_validator_class.return_value = mock_validator
    # No lanza excepción = válido

    result = runner.invoke(cli, ["validate-sql", "SELECT * FROM sales"])

    assert result.exit_code == 0
    assert "válido" in result.output.lower() or "valid" in result.output.lower()


@patch("src.cli.load_schema")
@patch("src.cli.SQLValidator")
def test_validate_sql_command_invalid(mock_validator_class, mock_schema, runner, sample_schema):
    """Test: Comando validate-sql con SQL inválido."""
    from src.utils.exceptions import InvalidTableError

    mock_schema.return_value = sample_schema
    mock_validator = MagicMock()
    mock_validator.validate_query.side_effect = InvalidTableError("unauthorized_table")
    mock_validator_class.return_value = mock_validator

    result = runner.invoke(cli, ["validate-sql", "SELECT * FROM unauthorized_table"])

    assert result.exit_code == 1
    assert "Error" in result.output or "invalid" in result.output.lower()
