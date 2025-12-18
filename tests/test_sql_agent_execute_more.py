"""More coverage for execute_query paths in src.agents.sql_agent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.agents import sql_agent


def test_execute_query_semantic_cache_hit_returns_result(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")

    agent = MagicMock()
    monkeypatch.setattr("src.agents.executor.get_semantic_cached_result", lambda q: ("cached", "SELECT 1"))

    out = sql_agent.execute_query(agent, "ventas por pais")
    assert out == "cached"
    agent.invoke.assert_not_called()


def test_execute_query_semantic_cache_hit_returns_metadata(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")

    agent = MagicMock()
    monkeypatch.setattr("src.agents.executor.get_semantic_cached_result", lambda q: ("cached", "SELECT 1"))

    out = sql_agent.execute_query(agent, "ventas por pais", return_metadata=True)
    assert isinstance(out, dict)
    assert out["cache_hit_type"] == "semantic"
    assert out["execution_time"] == 0.0


def test_execute_query_semantic_cache_error_falls_back(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")

    def boom(_q: str):
        raise Exception("boom")

    monkeypatch.setattr("src.agents.executor.get_semantic_cached_result", boom)

    agent = MagicMock()
    agent.invoke.return_value = {"messages": [AIMessage(content="ok")]}

    out = sql_agent.execute_query(agent, "ventas por pais")
    assert out == "ok"


def test_execute_query_streaming_calls_callback_and_returns_tool_result(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")

    sql_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT 1"}}],
    )
    tool_msg = ToolMessage(content="data rows", tool_call_id="call1")
    chunks = [{"agent": {"messages": [sql_msg]}}, {"agent": {"messages": [tool_msg]}}]

    def stream(_payload):
        for c in chunks:
            yield c

    agent = MagicMock()
    agent.stream.side_effect = stream

    cb = MagicMock()
    out = sql_agent.execute_query(agent, "q", stream=True, stream_callback=cb, prefer_analysis=False)
    assert out == "data rows"
    assert cb.call_count >= 2


def test_execute_query_prefers_analysis_when_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")

    sql_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT 1"}}],
    )
    analysis_text = (
        "Análisis: "
        "Este es un análisis suficientemente largo para activar la heurística. "
        "Incluye tendencias, comparaciones e insights relevantes para el usuario. "
        "Además, contiene más de veinte palabras para marcarse como análisis."
    )
    analysis_msg = AIMessage(content=analysis_text)
    agent = MagicMock()
    agent.invoke.return_value = {"messages": [sql_msg, analysis_msg]}

    out = sql_agent.execute_query(agent, "q", prefer_analysis=True)
    assert "Análisis:" in out


def test_execute_query_extracts_token_usage_and_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")

    sql_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT 1"}}],
    )
    sql_msg.response_metadata = {
        "token_usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        "model": "test-model",
    }

    tool_msg = ToolMessage(content="ok", tool_call_id="call1")
    agent = MagicMock()
    agent.invoke.return_value = {"messages": [sql_msg, tool_msg]}

    out = sql_agent.execute_query(agent, "q", return_metadata=True, prefer_analysis=False)
    assert out["tokens_input"] == 1
    assert out["tokens_output"] == 2
    assert out["tokens_total"] == 3
    assert out["model_used"] == "test-model"


def test_execute_query_fallback_str_result_when_message_has_no_content(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")

    agent = MagicMock()
    agent.invoke.return_value = {"messages": [object()]}

    out = sql_agent.execute_query(agent, "q")
    assert "messages" in out


def test_execute_query_fallback_str_result_when_no_messages(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")

    agent = MagicMock()
    agent.invoke.return_value = {}

    out = sql_agent.execute_query(agent, "q")
    assert out == "{}"


def test_execute_query_fallback_uses_first_message_content_when_tool_call_only(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")

    sql_only = AIMessage(
        content="primero",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT 1"}}],
    )
    agent = MagicMock()
    agent.invoke.return_value = {"messages": [sql_only]}

    out = sql_agent.execute_query(agent, "q")
    assert out == "primero"


def test_execute_query_handles_semantic_cache_set_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")

    sql_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT 1"}}],
    )
    tool_msg = ToolMessage(content="ok", tool_call_id="call1")

    agent = MagicMock()
    agent.invoke.return_value = {"messages": [sql_msg, tool_msg]}

    monkeypatch.setattr("src.agents.executor.set_semantic_cached_result", lambda *_a, **_k: (_ for _ in ()).throw(Exception("boom")))

    out = sql_agent.execute_query(agent, "q")
    assert out == "ok"


def test_execute_query_records_sql_cache_hit_type(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")

    sql_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT 1"}}],
    )
    tool_msg = ToolMessage(content="[(1,)]", tool_call_id="call1")
    agent = MagicMock()

    rec = MagicMock()
    monkeypatch.setattr("src.agents.executor.record_query_performance", rec)

    def invoke(_payload):
        # Simula que la herramienta ejecutó desde cache SQL.
        sql_agent._SQL_EXECUTION_INFO.set(("SELECT 1", True))
        return {"messages": [sql_msg, tool_msg]}

    agent.invoke.side_effect = invoke

    out = sql_agent.execute_query(agent, "q")
    assert out == "[(1,)]"
    assert rec.call_args.kwargs["cache_hit_type"] == "sql"


def test_execute_query_performance_metrics_error_is_caught(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "false")

    sql_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT 1"}}],
    )
    tool_msg = ToolMessage(content="[(1,)]", tool_call_id="call1")
    agent = MagicMock()
    agent.invoke.return_value = {"messages": [sql_msg, tool_msg]}

    def boom(*_a, **_k):
        raise Exception("perf boom")

    monkeypatch.setattr("src.agents.executor.record_query_performance", boom)

    out = sql_agent.execute_query(agent, "q")
    assert out == "[(1,)]"
