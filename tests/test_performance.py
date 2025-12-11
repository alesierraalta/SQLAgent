"""Pruebas de rendimiento/latencia (mockeadas) para rutas rápidas."""

import os
import time

import pytest
from langchain_core.messages import AIMessage

from src.agents import sql_agent
from src.agents.sql_agent import execute_query


@pytest.mark.perf
def test_execute_query_semantic_cache_latency(monkeypatch):
    """Cache semántico debe responder en <50ms sin tocar el agente."""
    os.environ["ENABLE_SEMANTIC_CACHE"] = "true"
    monkeypatch.setattr(sql_agent, "get_semantic_cached_result", lambda q: ("cached-result", "SELECT 1"))

    t0 = time.perf_counter()
    result = execute_query(agent=None, question="ping", return_metadata=True, stream=False)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.05
    assert result["cache_hit_type"] == "semantic"
    assert result["response"] == "cached-result"
    assert result["sql_generated"] == "SELECT 1"


class DummyAgent:
    def invoke(self, payload):
        return {
            "messages": [
                AIMessage(
                    content="ok",
                    response_metadata={
                        "token_usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 1,
                            "total_tokens": 2,
                        },
                        "model": "gpt-4o",
                    },
                )
            ]
        }


@pytest.mark.perf
def test_execute_query_agent_latency_budget(monkeypatch):
    """Ruta normal con agente mock debe responder en <200ms."""
    monkeypatch.setattr(sql_agent, "get_semantic_cached_result", lambda q: None)
    monkeypatch.setattr(sql_agent, "get_cached_result", lambda sql: None)

    t0 = time.perf_counter()
    result = execute_query(agent=DummyAgent(), question="simple question", return_metadata=True, stream=False)
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.2
    assert result["response"] == "ok"
    assert result["tokens_total"] == 2
    assert result["cache_hit_type"] == "none"
