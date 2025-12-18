"""Tests para la herramienta validated_sql_query dentro de create_sql_agent."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.agents import sql_agent


def _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool):
    """Crea agente y retorna la función validated_sql_query (sin wrapper)."""
    captured = {}

    # Evitar wrapper de LangChain tools: mantener función pura
    monkeypatch.setattr("src.agents.tools.tool_decorator", lambda f: f)

    def fake_create_agent(_llm, tools, system_prompt=None):
        captured["tools"] = tools
        return MagicMock()

    monkeypatch.setattr("src.agents.builder.create_agent", fake_create_agent)

    llm = MagicMock()
    llm.bind_tools.return_value = llm
    monkeypatch.setattr("src.agents.builder.get_chat_model", lambda **kwargs: llm)
    monkeypatch.setattr("src.agents.builder.SQLDatabase", lambda engine: SimpleNamespace(dialect="postgresql"))

    toolkit_instance = MagicMock()
    toolkit_instance.get_tools.return_value = [sql_tool]
    monkeypatch.setattr("src.agents.builder.SQLDatabaseToolkit", lambda db, llm: toolkit_instance)

    validator_instance = MagicMock()
    validator_instance.validate_query.return_value = None
    monkeypatch.setattr("src.agents.builder.SQLValidator", lambda schema: validator_instance)

    monkeypatch.setattr("src.agents.prompts.get_relevant_examples", lambda *a, **k: [])
    monkeypatch.setattr("src.agents.prompts.format_examples_for_prompt", lambda *a, **k: "")
    monkeypatch.setattr("src.agents.builder.classify_query_complexity_ml", lambda q: "simple")

    sql_agent.create_sql_agent(mock_engine, sample_schema, llm=None, question="q")

    validated = next(t for t in captured["tools"] if callable(t) and t.__name__ == "validated_sql_query")
    return validated, sql_tool, validator_instance


def test_validated_sql_query_returns_cached_result(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"

    validated, tool, _validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)

    monkeypatch.setattr("src.agents.tools.get_cached_result", lambda q: "cached")
    monkeypatch.setattr("src.agents.tools.set_cached_result", MagicMock())

    out = validated("SELECT * FROM sales")
    assert out == "cached"
    tool.invoke.assert_not_called()


def test_validated_sql_query_formats_empty_result(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"
    sql_tool.invoke.return_value = "[]"

    validated, _tool, _validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)

    monkeypatch.setattr("src.agents.tools.get_cached_result", lambda q: None)
    set_mock = MagicMock()
    monkeypatch.setattr("src.agents.tools.set_cached_result", set_mock)
    monkeypatch.setattr("src.agents.tools.record_query_metrics", MagicMock())

    out = validated("SELECT * FROM sales")
    assert "No se encontraron datos" in out
    set_mock.assert_called_once()


def test_validated_sql_query_caches_non_empty_result(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"
    sql_tool.invoke.return_value = "data"

    validated, _tool, _validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)

    monkeypatch.setattr("src.agents.tools.get_cached_result", lambda q: None)
    set_mock = MagicMock()
    monkeypatch.setattr("src.agents.tools.set_cached_result", set_mock)
    monkeypatch.setattr("src.agents.tools.record_query_metrics", MagicMock())

    out = validated("SELECT * FROM sales")
    assert out == "data"
    set_mock.assert_called_once()


def test_validated_sql_query_attempts_recovery_on_db_error(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"
    sql_tool.invoke.side_effect = [Exception("column does not exist"), "ok"]

    validated, _tool, validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)

    monkeypatch.setattr("src.agents.tools.get_cached_result", lambda q: None)
    monkeypatch.setattr("src.agents.tools.set_cached_result", MagicMock())
    monkeypatch.setattr("src.agents.tools.should_attempt_recovery", lambda msg: True)
    monkeypatch.setattr("src.agents.tools.recover_from_error", lambda q, err, schema_info: "SELECT id FROM sales")
    monkeypatch.setattr("src.agents.tools.record_query_metrics", MagicMock())
    monkeypatch.setattr("src.agents.error_recovery.report_successful_correction", MagicMock())

    out = validated("SELECT bad FROM sales")
    assert out == "ok"
    validator.validate_query.assert_called()  # se valida SQL corregido


def test_validated_sql_query_returns_error_when_recovery_disabled(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"
    sql_tool.invoke.side_effect = Exception("permission denied")

    validated, _tool, _validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)

    monkeypatch.setattr("src.agents.tools.get_cached_result", lambda q: None)
    monkeypatch.setattr("src.agents.tools.should_attempt_recovery", lambda msg: False)

    out = validated("SELECT * FROM sales")
    assert "Error al ejecutar query en BD" in out


def test_validated_sql_query_handles_validation_error(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"

    validated, _tool, validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)
    validator.validate_query.side_effect = Exception("invalid")

    out = validated("SELECT * FROM sales")
    assert out.startswith("Error al ejecutar query:")


def test_validated_sql_query_recovery_empty_result(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"
    sql_tool.invoke.side_effect = [Exception("missing column"), "[]"]

    validated, _tool, validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)

    monkeypatch.setattr("src.agents.tools.get_cached_result", lambda q: None)
    set_mock = MagicMock()
    monkeypatch.setattr("src.agents.tools.set_cached_result", set_mock)
    monkeypatch.setattr("src.agents.tools.should_attempt_recovery", lambda msg: True)
    monkeypatch.setattr("src.agents.tools.recover_from_error", lambda q, err, schema_info: "SELECT id FROM sales WHERE 1=0")
    monkeypatch.setattr("src.agents.tools.record_query_metrics", MagicMock())
    monkeypatch.setattr("src.agents.error_recovery.report_successful_correction", MagicMock())

    out = validated("SELECT bad FROM sales")
    assert "No se encontraron datos" in out
    validator.validate_query.assert_called()
    set_mock.assert_called()


def test_validated_sql_query_recovery_corrected_fails_validation(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"
    sql_tool.invoke.side_effect = Exception("missing column")

    validated, _tool, validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)
    validator.validate_query.side_effect = [None, Exception("invalid corrected")]

    monkeypatch.setattr("src.agents.tools.get_cached_result", lambda q: None)
    monkeypatch.setattr("src.agents.tools.should_attempt_recovery", lambda msg: True)
    monkeypatch.setattr("src.agents.tools.recover_from_error", lambda q, err, schema_info: "SELECT invalid FROM sales")

    out = validated("SELECT bad FROM sales")
    assert "Error al ejecutar query en BD" in out


def test_validated_sql_query_recovery_no_corrected_sql(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"
    sql_tool.invoke.side_effect = Exception("missing column")

    validated, _tool, _validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)

    monkeypatch.setattr("src.agents.tools.get_cached_result", lambda q: None)
    monkeypatch.setattr("src.agents.tools.should_attempt_recovery", lambda msg: True)
    monkeypatch.setattr("src.agents.tools.recover_from_error", lambda q, err, schema_info: q)  # same as original

    out = validated("SELECT bad FROM sales")
    assert "Error al ejecutar query en BD" in out


def test_validated_sql_query_recovery_raises(monkeypatch, sample_schema, mock_engine):
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"
    sql_tool.invoke.side_effect = Exception("missing column")

    validated, _tool, _validator = _make_validated_tool(monkeypatch, sample_schema, mock_engine, sql_tool)

    monkeypatch.setattr("src.agents.tools.get_cached_result", lambda q: None)
    monkeypatch.setattr("src.agents.tools.should_attempt_recovery", lambda msg: True)

    def boom(*_args, **_kwargs):
        raise Exception("recovery boom")

    monkeypatch.setattr("src.agents.tools.recover_from_error", boom)

    out = validated("SELECT bad FROM sales")
    assert "Error al ejecutar query en BD" in out
