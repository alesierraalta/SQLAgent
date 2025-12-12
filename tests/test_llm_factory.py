"""Tests para el factory multi-proveedor de LLMs."""

from types import SimpleNamespace

import pytest

from src.utils import llm_factory


def test_normalize_provider_aliases():
    assert llm_factory.normalize_provider("gemini") == "google"
    assert llm_factory.normalize_provider("google") == "google"
    assert llm_factory.normalize_provider("openai") == "openai"


def test_get_default_model_name_prefers_llm_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_MODEL", "x-model")
    monkeypatch.setenv("OPENAI_MODEL", "y-model")
    assert llm_factory.get_default_model_name("openai") == "x-model"


def test_get_default_model_name_openai_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "my-model")
    assert llm_factory.get_default_model_name("openai") == "my-model"


def test_bind_tools_safe_falls_back_when_tool_choice_not_supported():
    class DummyLLM:
        def bind_tools(self, tools, **kwargs):
            if "tool_choice" in kwargs:
                raise TypeError("tool_choice not supported")
            return "bound"

    out = llm_factory.bind_tools_safe(DummyLLM(), tools=[1], tool_choice="any")
    assert out == "bound"


def test_bind_tools_safe_raises_without_bind_tools():
    with pytest.raises(ValueError):
        llm_factory.bind_tools_safe(SimpleNamespace(), tools=[], tool_choice="any")


def test_get_chat_model_unsupported_provider_raises():
    with pytest.raises(ValueError):
        llm_factory.get_chat_model(provider="wat")

