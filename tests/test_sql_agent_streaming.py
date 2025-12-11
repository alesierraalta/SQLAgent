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
