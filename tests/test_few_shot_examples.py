"""Tests para few_shot_examples."""

import pytest

from src.utils import few_shot_examples


def test_detect_query_type_branches():
    assert few_shot_examples._detect_query_type("Top 5 productos") == "top_n"
    assert few_shot_examples._detect_query_type("Join entre ventas y productos") == "join"
    assert few_shot_examples._detect_query_type("Total por país") == "group_by"
    assert few_shot_examples._detect_query_type("Revenue donde país = X") == "filter"
    assert few_shot_examples._detect_query_type("count sales") == "aggregation"


def test_get_relevant_examples_respects_flag(monkeypatch):
    monkeypatch.setenv("ENABLE_FEW_SHOT", "false")
    assert few_shot_examples.get_relevant_examples("Total ventas") == []


def test_get_relevant_examples_limits_count(monkeypatch):
    monkeypatch.setenv("ENABLE_FEW_SHOT", "true")
    ex = few_shot_examples.get_relevant_examples("Total de ventas por país", max_examples=1)
    assert len(ex) <= 1


def test_format_examples_for_prompt_empty():
    assert few_shot_examples.format_examples_for_prompt([]) == ""
