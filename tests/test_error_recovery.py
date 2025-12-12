"""Tests para recuperación automática de errores SQL."""

from types import SimpleNamespace

import pytest

from src.agents import error_recovery


def test_classify_error_branches():
    assert error_recovery._classify_error("column 'x' does not exist") == "COLUMN_NOT_FOUND"
    assert error_recovery._classify_error("table foo does not exist") == "TABLE_NOT_FOUND"
    assert error_recovery._classify_error("syntax error at or near") == "SYNTAX_ERROR"
    assert error_recovery._classify_error("type mismatch") == "TYPE_MISMATCH"
    assert error_recovery._classify_error("must appear in group by") == "AGGREGATE_ERROR"
    assert error_recovery._classify_error("join error relation") == "JOIN_ERROR"
    assert error_recovery._classify_error("otro error") == "UNKNOWN_ERROR"


def test_should_attempt_recovery_non_recoverable():
    assert error_recovery.should_attempt_recovery("permission denied") is False
    assert error_recovery.should_attempt_recovery("authentication failed") is False


def test_should_attempt_recovery_recoverable():
    assert error_recovery.should_attempt_recovery("column does not exist") is True
    assert error_recovery.should_attempt_recovery("syntax error") is True


def test_clean_sql_response_extracts_code_block():
    resp = "```sql\nSELECT * FROM sales\n```"
    assert error_recovery._clean_sql_response(resp).strip() == "SELECT * FROM sales"


def test_recover_from_error_returns_known_pattern(monkeypatch):
    fake_store = SimpleNamespace(find_correction=lambda **k: "SELECT 1")
    monkeypatch.setattr("src.utils.error_patterns.get_error_pattern_store", lambda: fake_store)

    monkeypatch.setattr(
        error_recovery,
        "get_chat_model",
        lambda *a, **k: (_ for _ in ()).throw(Exception("should not call")),
    )

    result = error_recovery.recover_from_error(
        original_sql="SELECT bad",
        error_message="column 'bad' does not exist",
        schema_info="sales(id)",
    )
    assert result == "SELECT 1"


def test_recover_from_error_uses_llm_when_no_pattern(monkeypatch):
    fake_store = SimpleNamespace(find_correction=lambda **k: None)
    monkeypatch.setattr("src.utils.error_patterns.get_error_pattern_store", lambda: fake_store)

    class DummyLLM:
        def invoke(self, prompt):
            return SimpleNamespace(content="```sql\nSELECT * FROM sales\n```")

    monkeypatch.setattr(error_recovery, "get_chat_model", lambda *a, **k: DummyLLM())

    result = error_recovery.recover_from_error(
        original_sql="SELECT bad",
        error_message="table 'bad' does not exist",
        schema_info="sales(id)",
    )
    assert result.strip() == "SELECT * FROM sales"


def test_report_successful_correction_calls_store(monkeypatch):
    calls = {}

    class FakeStore:
        def store_successful_correction(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr("src.utils.error_patterns.get_error_pattern_store", lambda: FakeStore())

    error_recovery.report_successful_correction(
        original_sql="SELECT bad",
        error_message="column 'bad' does not exist",
        corrected_sql="SELECT id FROM sales",
    )

    assert calls["error_type"] == "COLUMN_NOT_FOUND"
    assert calls["corrected_sql"] == "SELECT id FROM sales"


def test_recover_from_error_returns_none_on_internal_exception(monkeypatch):
    monkeypatch.setattr(
        "src.utils.error_patterns.get_error_pattern_store",
        lambda: (_ for _ in ()).throw(Exception("boom")),
    )

    assert (
        error_recovery.recover_from_error(
            original_sql="SELECT bad",
            error_message="boom",
            schema_info="sales(id)",
        )
        is None
    )


def test_clean_sql_response_filters_explanations():
    resp = """Aquí hay una explicación.
SELECT id
FROM sales
WHERE id = 1
revenue > 0
-- comentario
"""
    cleaned = error_recovery._clean_sql_response(resp)
    assert "SELECT id" in cleaned
    assert "FROM sales" in cleaned


def test_should_attempt_recovery_defaults_true_for_unknown():
    assert error_recovery.should_attempt_recovery("algo raro") is True
