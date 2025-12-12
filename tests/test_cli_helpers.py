"""Tests for non-interactive helpers in src.cli."""

from __future__ import annotations

from decimal import Decimal

import pytest
from rich.console import Console

from src.cli import (
    StreamingDisplay,
    _extract_column_names_from_sql,
    _format_value,
    _generate_automatic_analysis,
    _infer_column_headers,
)


def test_extract_column_names_from_sql_with_aliases():
    sql = "SELECT country AS country_name, SUM(revenue) AS total_revenue FROM sales"
    headers = _extract_column_names_from_sql(sql, 2)
    assert headers == ["Country Name", "Total Revenue"]


def test_extract_column_names_from_sql_handles_functions_no_alias():
    sql = "SELECT country, SUM(revenue) FROM sales"
    headers = _extract_column_names_from_sql(sql, 2)
    # country -> Country, SUM(revenue) -> Total Revenue
    assert headers == ["Country", "Total Revenue"]


def test_extract_column_names_returns_none_on_unparseable_sql():
    assert _extract_column_names_from_sql("INVALID", 1) is None


def test_infer_column_headers_numeric_patterns():
    data = [
        [1, 2000, 3],
        [2, 5000, 4],
    ]
    headers = _infer_column_headers(data, 3)
    assert headers[0] == "ID"
    assert headers[1] == "Total Vendido"
    assert headers[2] == "Stock / Inventario"


def test_infer_column_headers_empty_data():
    assert _infer_column_headers([], 2) == ["Columna 1", "Columna 2"]


def test_format_value_various_types():
    assert _format_value(None) == "N/A"
    assert _format_value(1000) == "1,000"
    assert _format_value(12.0) == "12"
    assert _format_value(12.5) == "12.50"
    assert _format_value(Decimal("10.00")) == "10"


def test_generate_automatic_analysis_basic_and_empty():
    assert "No hay datos" in _generate_automatic_analysis([])
    data = [("USA", 100, 50), ("Canada", 200, 60)]
    analysis = _generate_automatic_analysis(data)
    assert "Se encontraron 2 registros" in analysis
    assert "valor m" in analysis.lower()


def test_streaming_display_update_sets_fields():
    display = StreamingDisplay()
    display.update({"type": "sql", "content": "SELECT 1"})
    assert display.sql == "SELECT 1"
    display.update({"type": "analysis", "content": "hi"})
    assert "hi" in display.analysis
    display.update({"type": "error", "content": "boom"})
    assert display.error == "boom"


def test_format_query_result_renders_table_and_analysis(monkeypatch: pytest.MonkeyPatch):
    import src.cli as cli_module

    rec_console = Console(record=True, width=120)
    monkeypatch.setattr(cli_module, "console", rec_console)

    response = '[("USA", 100), ("CA", 50)]'
    cli_module._format_query_result(
        response,
        output_format="table",
        sql_generated="SELECT country, SUM(revenue) FROM sales",
        question="ventas por pais",
    )
    out = rec_console.export_text()
    assert "USA" in out
    assert "CA" in out


def test_format_query_result_handles_dict(monkeypatch: pytest.MonkeyPatch):
    import src.cli as cli_module

    rec_console = Console(record=True, width=80)
    monkeypatch.setattr(cli_module, "console", rec_console)

    cli_module._format_query_result('{"a": 1, "b": 2}', output_format="table")
    out = rec_console.export_text()
    assert "a" in out and "b" in out
