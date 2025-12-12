"""Tests para agentes de explicación de queries."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.agents import query_explainer


def test_get_explain_plan_success():
    engine = MagicMock()
    conn = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = conn
    cm.__exit__.return_value = False
    engine.connect.return_value = cm
    conn.execute.return_value = [("Seq Scan on sales",), ("Filter: revenue > 0",)]

    plan = query_explainer._get_explain_plan("SELECT * FROM sales", engine)
    assert "Seq Scan" in plan


def test_get_explain_plan_failure_returns_message():
    engine = MagicMock()
    engine.connect.side_effect = Exception("fail")

    plan = query_explainer._get_explain_plan("SELECT 1", engine)
    assert "Error al obtener plan de ejecución" in plan


def test_explain_query_uses_llm(monkeypatch):
    engine = MagicMock()
    monkeypatch.setattr(query_explainer, "_get_explain_plan", lambda sql, eng: "plan")

    class DummyLLM:
        def invoke(self, prompt):
            return SimpleNamespace(content="explicación")

    monkeypatch.setattr(query_explainer, "get_chat_model", lambda *a, **k: DummyLLM())

    out = query_explainer.explain_query("SELECT 1", engine)
    assert out == "explicación"


def test_explain_query_handles_llm_exception(monkeypatch):
    engine = MagicMock()
    monkeypatch.setattr(query_explainer, "_get_explain_plan", lambda sql, eng: "plan")

    class DummyLLM:
        def invoke(self, prompt):
            raise Exception("boom")

    monkeypatch.setattr(query_explainer, "get_chat_model", lambda *a, **k: DummyLLM())

    out = query_explainer.explain_query("SELECT 1", engine)
    assert "Error al generar explicación" in out


def test_explain_query_simple_success(monkeypatch):
    class DummyLLM:
        def invoke(self, prompt):
            return SimpleNamespace(content="simple")

    monkeypatch.setattr(query_explainer, "get_chat_model", lambda *a, **k: DummyLLM())
    assert query_explainer.explain_query_simple("SELECT 1") == "simple"


def test_explain_query_simple_handles_exception(monkeypatch):
    class DummyLLM:
        def invoke(self, prompt):
            raise Exception("boom")

    monkeypatch.setattr(query_explainer, "get_chat_model", lambda *a, **k: DummyLLM())
    out = query_explainer.explain_query_simple("SELECT 1")
    assert "Error al generar explicación" in out
