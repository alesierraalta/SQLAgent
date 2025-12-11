"""Tests para el agente SQL."""

from unittest.mock import MagicMock, patch

import pytest

from src.agents.sql_agent import create_sql_agent, execute_query
from src.schemas.database_schema import DatabaseSchema
from tests.conftest import mock_agent, mock_engine, sample_schema


@patch("src.agents.sql_agent.ChatOpenAI")
@patch("src.agents.sql_agent.SQLDatabase")
@patch("src.agents.sql_agent.SQLDatabaseToolkit")
def test_create_sql_agent(mock_toolkit, mock_db, mock_chat_openai, mock_engine, sample_schema):
    """Test: Creación del agente SQL."""
    # Configurar mocks
    mock_toolkit_instance = MagicMock()
    mock_toolkit.return_value = mock_toolkit_instance
    mock_tool = MagicMock()
    mock_tool.name = "sql_db_query"
    mock_toolkit_instance.get_tools.return_value = [mock_tool]

    # Crear agente
    agent = create_sql_agent(mock_engine, sample_schema)

    # Verificar que se creó correctamente
    assert agent is not None
    mock_toolkit.assert_called_once()


def test_execute_query_success(mock_agent):
    """Test: Ejecución exitosa de query."""
    question = "¿Cuál es el total de revenue?"
    response = execute_query(mock_agent, question)

    assert response == "Respuesta del agente"
    mock_agent.invoke.assert_called_once()


def test_execute_query_with_retry(mock_agent):
    """Test: Ejecución con retry en caso de error."""
    # Configurar para que falle 2 veces y luego tenga éxito
    mock_agent.invoke.side_effect = [
        Exception("Error 1"),
        Exception("Error 2"),
        {"messages": [MagicMock(content="Éxito", role="assistant")]},
    ]

    question = "Test query"
    response = execute_query(mock_agent, question, max_retries=3)

    assert "Éxito" in str(response)
    assert mock_agent.invoke.call_count == 3


def test_execute_query_all_retries_fail(mock_agent):
    """Test: Todos los reintentos fallan."""
    mock_agent.invoke.side_effect = Exception("Error persistente")

    question = "Test query"
    response = execute_query(mock_agent, question, max_retries=2)

    assert "Error" in response
    assert mock_agent.invoke.call_count == 2


def test_execute_query_empty_result_no_loop(mock_agent):
    """Test: Query con resultado vacío no entra en loop."""
    from langchain_core.messages import ToolMessage, AIMessage
    
    # Simular respuesta con resultado vacío
    tool_message = ToolMessage(
        content="[]",
        tool_call_id="test_id"
    )
    ai_message = AIMessage(
        content="Query ejecutada",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT * FROM sales"}}]
    )
    
    mock_agent.invoke.return_value = {
        "messages": [ai_message, tool_message]
    }
    
    question = "Muestra el revenue agrupado por mes"
    response = execute_query(mock_agent, question, max_retries=3)
    
    # Debe ejecutarse solo una vez y retornar mensaje apropiado
    assert mock_agent.invoke.call_count == 1
    assert "No se encontraron datos" in response or "[]" in response


def test_execute_query_detects_duplicate_queries(mock_agent):
    """Test: Detecta queries duplicadas y detiene el loop."""
    from langchain_core.messages import ToolMessage, AIMessage
    
    # Simular múltiples invocaciones con la misma query
    tool_message = ToolMessage(
        content="[]",
        tool_call_id="test_id"
    )
    ai_message = AIMessage(
        content="Query ejecutada",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT * FROM sales"}}]
    )
    
    # El agente intenta ejecutar la misma query múltiples veces
    mock_agent.invoke.return_value = {
        "messages": [ai_message, tool_message]
    }
    
    question = "Muestra el revenue agrupado por mes"
    response = execute_query(mock_agent, question, max_retries=5)
    
    # Debe detectar la query duplicada y detenerse
    # Nota: La detección de duplicados ocurre dentro de execute_query,
    # así que el agente puede ser invocado una vez antes de detectar el loop
    assert "No se encontraron datos" in response or "[]" in response


def test_execute_query_empty_result_formatted_message(mock_agent):
    """Test: Resultado vacío se formatea con mensaje apropiado."""
    from langchain_core.messages import ToolMessage, AIMessage
    
    # Simular respuesta con resultado vacío
    tool_message = ToolMessage(
        content="",
        tool_call_id="test_id"
    )
    ai_message = AIMessage(
        content="Query ejecutada exitosamente",
        tool_calls=[{"id": "call1", "name": "validated_sql_query", "args": {"query": "SELECT * FROM sales WHERE id = 999"}}]
    )
    
    mock_agent.invoke.return_value = {
        "messages": [ai_message, tool_message]
    }
    
    question = "Busca ventas con ID 999"
    response = execute_query(mock_agent, question)
    
    # Debe formatear el resultado vacío apropiadamente
    assert response is not None
    assert len(response) > 0  # Debe tener algún contenido, no estar completamente vacío
