"""Tests adicionales para create_sql_agent y helpers."""

from unittest.mock import MagicMock, patch

import pytest

from src.agents import sql_agent
from src.schemas.database_schema import ColumnSchema, DatabaseSchema, TableSchema


def test_select_candidate_tables_and_render_subset(sample_schema):
    names = sql_agent._select_candidate_tables(sample_schema, "ventas por pais en sales", max_tables=2)
    assert "sales" in names

    subset = sql_agent._render_schema_subset(sample_schema, ["sales", "unknown"])
    assert "sales:" in subset
    assert "unknown" not in subset


def test_select_candidate_tables_uses_table_description():
    schema = DatabaseSchema(
        tables={
            "t1": TableSchema(
                name="t1",
                description="ventas por pais",
                columns=[ColumnSchema(name="country", type="TEXT", nullable=True)],
                primary_key=[],
            )
        }
    )
    names = sql_agent._select_candidate_tables(schema, "ventas por pais", max_tables=3)
    assert names == ["t1"]


def test_classify_query_complexity_heuristic():
    assert sql_agent._classify_query_complexity("hacer join entre sales y products") == "complex"
    assert sql_agent._classify_query_complexity("total revenue por pais") == "simple"
    assert sql_agent._classify_query_complexity("count ventas") == "simple"
    assert sql_agent._classify_query_complexity("esto es una pregunta larga sin keywords especiales") == "complex"


def test_generate_system_prompt_includes_relevant_subset(sample_schema, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_COMPACT_SCHEMA", "true")
    monkeypatch.setenv("SCHEMA_MAX_TABLES", "6")
    prompt = sql_agent._generate_system_prompt(sample_schema, "postgresql", question="ventas por country en sales")
    assert "(Subconjunto relevante)" in prompt
    assert "sales:" in prompt


@patch("src.agents.builder.create_agent")
@patch("src.agents.builder.get_chat_model")
@patch("src.agents.builder.SQLDatabase")
@patch("src.agents.builder.SQLDatabaseToolkit")
def test_create_sql_agent_uses_fast_model_for_simple_question(
    mock_toolkit, mock_db, mock_get_chat_model, mock_create_agent, mock_engine, sample_schema, monkeypatch
):
    monkeypatch.setenv("USE_FAST_MODEL", "true")
    monkeypatch.setenv("FAST_MODEL", "fast-model")
    monkeypatch.setenv("COMPLEX_MODEL", "complex-model")
    monkeypatch.setattr("src.agents.builder.classify_query_complexity_ml", lambda q: "simple")

    llm_instance = MagicMock()
    llm_instance.bind_tools.return_value = llm_instance
    mock_get_chat_model.return_value = llm_instance

    toolkit_instance = MagicMock()
    mock_toolkit.return_value = toolkit_instance
    tool = MagicMock()
    tool.name = "sql_db_query"
    toolkit_instance.get_tools.return_value = [tool]

    mock_create_agent.return_value = MagicMock()

    sql_agent.create_sql_agent(mock_engine, sample_schema, llm=None, question="total ventas")

    assert mock_get_chat_model.call_args.kwargs["model_name"] == "fast-model"


@patch("src.agents.builder.create_agent")
@patch("src.agents.builder.get_chat_model")
@patch("src.agents.builder.SQLDatabase")
@patch("src.agents.builder.SQLDatabaseToolkit")
def test_create_sql_agent_uses_complex_model_for_complex_question(
    mock_toolkit, mock_db, mock_get_chat_model, mock_create_agent, mock_engine, sample_schema, monkeypatch
):
    monkeypatch.setenv("USE_FAST_MODEL", "true")
    monkeypatch.setenv("FAST_MODEL", "fast-model")
    monkeypatch.setenv("COMPLEX_MODEL", "complex-model")

    monkeypatch.setattr("src.agents.builder.classify_query_complexity_ml", lambda q: "complex")

    llm_instance = MagicMock()
    llm_instance.bind_tools.return_value = llm_instance
    mock_get_chat_model.return_value = llm_instance

    toolkit_instance = MagicMock()
    mock_toolkit.return_value = toolkit_instance
    tool = MagicMock()
    tool.name = "sql_db_query"
    toolkit_instance.get_tools.return_value = [tool]
    mock_create_agent.return_value = MagicMock()

    sql_agent.create_sql_agent(mock_engine, sample_schema, llm=None, question="consulta compleja")

    assert mock_get_chat_model.call_args.kwargs["model_name"] == "complex-model"


@patch("src.agents.builder.create_agent")
@patch("src.agents.builder.get_chat_model")
@patch("src.agents.builder.SQLDatabase")
@patch("src.agents.builder.SQLDatabaseToolkit")
def test_create_sql_agent_default_model_when_fast_disabled(
    mock_toolkit, mock_db, mock_get_chat_model, mock_create_agent, mock_engine, sample_schema, monkeypatch
):
    monkeypatch.setenv("USE_FAST_MODEL", "false")
    monkeypatch.setenv("OPENAI_MODEL", "default-model")

    monkeypatch.setattr("src.agents.builder.classify_query_complexity_ml", lambda q: (_ for _ in ()).throw(Exception("should not call")))

    llm_instance = MagicMock()
    llm_instance.bind_tools.return_value = llm_instance
    mock_get_chat_model.return_value = llm_instance

    toolkit_instance = MagicMock()
    mock_toolkit.return_value = toolkit_instance
    tool = MagicMock()
    tool.name = "sql_db_query"
    toolkit_instance.get_tools.return_value = [tool]
    mock_create_agent.return_value = MagicMock()

    sql_agent.create_sql_agent(mock_engine, sample_schema, llm=None, question="algo")

    assert mock_get_chat_model.call_args.kwargs["model_name"] == "default-model"


@patch("src.agents.builder.SQLDatabase")
@patch("src.agents.builder.SQLDatabaseToolkit")
def test_create_sql_agent_raises_if_sql_tool_missing(
    mock_toolkit, mock_db, mock_engine, sample_schema
):
    toolkit_instance = MagicMock()
    mock_toolkit.return_value = toolkit_instance
    bad_tool = MagicMock()
    bad_tool.name = "other_tool"
    toolkit_instance.get_tools.return_value = [bad_tool]

    with pytest.raises(ValueError):
        sql_agent.create_sql_agent(mock_engine, sample_schema, llm=MagicMock())


@patch("src.agents.builder.create_agent")
@patch("src.agents.builder.get_chat_model")
@patch("src.agents.builder.SQLDatabase")
@patch("src.agents.builder.SQLDatabaseToolkit")
def test_create_sql_agent_keeps_non_sql_tools(
    mock_toolkit, mock_db, mock_get_chat_model, mock_create_agent, mock_engine, sample_schema, monkeypatch
):
    monkeypatch.setattr(sql_agent, "tool_decorator", lambda f: f)
    monkeypatch.setattr("src.agents.builder.classify_query_complexity_ml", lambda q: "simple")
    monkeypatch.setenv("USE_FAST_MODEL", "false")

    llm_instance = MagicMock()
    llm_instance.bind_tools.return_value = llm_instance
    mock_get_chat_model.return_value = llm_instance

    toolkit_instance = MagicMock()
    mock_toolkit.return_value = toolkit_instance
    sql_tool = MagicMock()
    sql_tool.name = "sql_db_query"
    other_tool = MagicMock()
    other_tool.name = "other_tool"
    toolkit_instance.get_tools.return_value = [sql_tool, other_tool]

    captured = {}

    def fake_create_agent(_llm, tools, system_prompt=None):
        captured["tools"] = tools
        return MagicMock()

    mock_create_agent.side_effect = fake_create_agent

    sql_agent.create_sql_agent(mock_engine, sample_schema, llm=None, question="q")

    assert other_tool in captured["tools"]