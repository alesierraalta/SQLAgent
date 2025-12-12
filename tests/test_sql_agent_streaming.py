from langchain_core.messages import AIMessage, ToolMessage

from src.agents.sql_agent import _parse_streaming_chunk


def test_parse_streaming_chunk_sql():
    msg = AIMessage(
        content="",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT 1"}}],
    )
    chunk = {"agent": {"messages": [msg]}}
    info = _parse_streaming_chunk(chunk, current_sql=None, current_response=None)
    assert info and info["type"] == "sql"
    assert info["sql"] == "SELECT 1"


def test_parse_streaming_chunk_execution():
    msg = ToolMessage(content="data rows", tool_call_id="call1")
    chunk = {"agent": {"messages": [msg]}}
    info = _parse_streaming_chunk(chunk, current_sql=None, current_response=None)
    assert info and info["type"] == "execution"
    assert info["content"] == "data rows"


def test_parse_streaming_chunk_analysis():
    msg = AIMessage(content="análisis largo de más de 50 caracteres para disparar parsing")
    chunk = {"agent": {"messages": [msg]}}
    info = _parse_streaming_chunk(chunk, current_sql=None, current_response=None)
    assert info and info["type"] == "analysis"


def test_parse_streaming_chunk_error():
    msg = ToolMessage(content="Error: boom", tool_call_id="call1")
    chunk = {"agent": {"messages": [msg]}}
    info = _parse_streaming_chunk(chunk, current_sql=None, current_response=None)
    assert info and info["type"] == "error"
    assert "boom" in info["content"]


def test_parse_streaming_chunk_partial_analysis():
    msg = AIMessage(content="texto parcial de análisis")
    chunk = {"agent": {"messages": [msg]}}
    info = _parse_streaming_chunk(chunk, current_sql=None, current_response=None)
    assert info and info["type"] == "analysis"
    assert "parcial" in info["content"]


def test_parse_streaming_chunk_handles_bad_input():
    assert _parse_streaming_chunk(None, current_sql=None, current_response=None) is None


def test_parse_streaming_chunk_returns_none_when_no_signal():
    msg = AIMessage(content="short")
    chunk = {"agent": {"messages": [msg]}}
    assert _parse_streaming_chunk(chunk, current_sql=None, current_response=None) is None
