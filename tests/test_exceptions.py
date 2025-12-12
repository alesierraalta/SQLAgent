"""Tests para excepciones personalizadas."""

from src.utils.exceptions import LLMError


def test_llm_error_stores_details():
    err = LLMError("boom", error_code="429", api_response={"error": "rate_limit"})
    assert err.message == "boom"
    assert err.details["error_code"] == "429"
    assert err.details["api_response"]["error"] == "rate_limit"
