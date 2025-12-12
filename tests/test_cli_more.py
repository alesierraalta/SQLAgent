"""Tests adicionales para CLI click (history, stats, ramas de query)."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.cli import cli
from src.utils.exceptions import SQLValidationError


@pytest.fixture
def runner():
    return CliRunner()


@patch("src.cli.clear_history")
def test_history_command_clear(mock_clear, runner):
    result = runner.invoke(cli, ["history", "--clear"])
    assert result.exit_code == 0
    mock_clear.assert_called_once()


@patch("src.cli.load_history")
def test_history_command_no_entries(mock_load, runner):
    mock_load.return_value = []
    result = runner.invoke(cli, ["history"])
    assert result.exit_code == 0
    assert "No hay historial" in result.output


@patch("src.cli.clear_performance_metrics")
def test_stats_command_clear(mock_clear, runner):
    result = runner.invoke(cli, ["stats", "--clear"])
    assert result.exit_code == 0
    mock_clear.assert_called_once()


@patch("src.cli.get_performance_stats")
def test_stats_command_no_metrics(mock_stats, runner):
    mock_stats.return_value = {"total_queries": 0}
    result = runner.invoke(cli, ["stats"])
    assert result.exit_code == 0
    assert "No hay métricas" in result.output


@patch("src.cli.load_schema")
@patch("src.cli.get_db_engine")
@patch("src.cli.create_sql_agent")
@patch("src.cli.execute_query")
@patch("src.utils.semantic_cache.initialize_semantic_cache")
@patch("src.cli.save_query")
@patch("src.cli.record_query_performance")
@patch("src.cli._format_query_result")
def test_query_command_verbose_metadata_dict(
    mock_format,
    mock_record_perf,
    mock_save,
    _mock_semantic_init,
    mock_execute,
    mock_create_agent,
    mock_engine,
    mock_schema,
    runner,
    sample_schema,
):
    mock_schema.return_value = sample_schema
    mock_engine.return_value = MagicMock()
    mock_create_agent.return_value = MagicMock()
    mock_execute.return_value = {
        "response": "ok",
        "sql_generated": "SELECT 1",
        "execution_time": 0.1,
        "success": True,
    }

    result = runner.invoke(cli, ["query", "pregunta", "--verbose"])
    assert result.exit_code == 0
    mock_execute.assert_called_once()
    mock_save.assert_called_once()
    mock_record_perf.assert_called_once()


@patch("src.cli.load_schema")
@patch("src.cli.get_db_engine")
@patch("src.cli.create_sql_agent")
@patch("src.cli.execute_query")
@patch("src.cli._display_streaming_response")
@patch("src.utils.semantic_cache.initialize_semantic_cache")
def test_query_command_explain_with_stream_prints_note(
    _mock_semantic_init,
    mock_display,
    mock_execute,
    mock_create_agent,
    mock_engine,
    mock_schema,
    runner,
    sample_schema,
):
    mock_schema.return_value = sample_schema
    mock_engine.return_value = MagicMock()
    mock_create_agent.return_value = MagicMock()
    mock_execute.return_value = "ok"

    dummy_display = MagicMock()
    mock_display.return_value = dummy_display

    result = runner.invoke(cli, ["query", "pregunta", "--explain", "--stream"])
    assert result.exit_code == 0
    assert "--explain no está disponible" in result.output


@patch("src.cli.load_schema")
@patch("src.cli.get_db_engine")
@patch("src.cli.create_sql_agent")
@patch("src.cli.execute_query")
@patch("src.utils.semantic_cache.initialize_semantic_cache")
def test_query_command_handles_sql_validation_error(
    _mock_semantic_init,
    mock_execute,
    mock_create_agent,
    mock_engine,
    mock_schema,
    runner,
    sample_schema,
):
    mock_schema.return_value = sample_schema
    mock_engine.return_value = MagicMock()
    mock_create_agent.return_value = MagicMock()
    mock_execute.side_effect = SQLValidationError("bad", details={"allowed_tables": ["sales"]})

    result = runner.invoke(cli, ["query", "pregunta"])
    assert result.exit_code == 1
    assert "Error de validación SQL" in result.output
