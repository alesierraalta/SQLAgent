"""Tests para módulo de performance."""

import json
from datetime import datetime, timedelta

import pytest

from src.utils import performance


@pytest.fixture
def temp_perf_file(tmp_path, monkeypatch):
    perf_file = tmp_path / "perf.json"
    monkeypatch.setattr(performance, "PERFORMANCE_FILE", perf_file)
    return perf_file


def test_record_query_performance_truncates_to_max(monkeypatch, temp_perf_file):
    monkeypatch.setattr(performance, "MAX_ENTRIES", 2)

    performance.record_query_performance("SELECT 1", 1.0)
    performance.record_query_performance("SELECT 2", 2.0)
    performance.record_query_performance("SELECT 3", 3.0)

    metrics = performance.load_performance_metrics()
    assert len(metrics) == 2
    assert metrics[-1]["sql"] == "SELECT 3"


def test_load_performance_metrics_invalid_json_returns_empty(temp_perf_file):
    temp_perf_file.write_text("{bad json", encoding="utf-8")
    assert performance.load_performance_metrics() == []


def test_get_performance_stats_empty_returns_zeros(monkeypatch, temp_perf_file):
    summary = performance.get_performance_stats(days=1)
    assert summary["total_queries"] == 0


def test_load_performance_metrics_limit_slices_last(temp_perf_file):
    now = datetime.now().isoformat()
    metrics = [
        {"timestamp": now, "sql": "A", "sql_hash": "a"},
        {"timestamp": now, "sql": "B", "sql_hash": "b"},
        {"timestamp": now, "sql": "C", "sql_hash": "c"},
    ]
    temp_perf_file.write_text(json.dumps(metrics), encoding="utf-8")
    assert performance.load_performance_metrics(limit=1)[0]["sql"] == "C"


def test_get_slow_queries_filters_success(temp_perf_file):
    now = datetime.now().isoformat()
    metrics = [
        {"timestamp": now, "sql": "SELECT 1", "sql_hash": "a", "execution_time": 10.0, "success": True},
        {"timestamp": now, "sql": "SELECT 2", "sql_hash": "b", "execution_time": 10.0, "success": False},
    ]
    temp_perf_file.write_text(json.dumps(metrics), encoding="utf-8")

    slow = performance.get_slow_queries(threshold_seconds=5.0)
    assert len(slow) == 1
    assert slow[0]["sql"] == "SELECT 1"


def test_get_query_patterns_groups_by_hash(temp_perf_file):
    now = datetime.now().isoformat()
    metrics = [
        {"timestamp": now, "sql": "SELECT 1", "sql_hash": "a", "execution_time": 1.0, "success": True},
        {"timestamp": now, "sql": "SELECT 1", "sql_hash": "a", "execution_time": 2.0, "success": True},
        {"timestamp": now, "sql": "SELECT 1", "sql_hash": "a", "execution_time": 3.0, "success": False},
    ]
    temp_perf_file.write_text(json.dumps(metrics), encoding="utf-8")

    patterns = performance.get_query_patterns(limit=5)
    assert patterns[0]["sql_hash"] == "a"
    assert patterns[0]["count"] == 3
    assert patterns[0]["fail_count"] == 1


def test_get_failed_queries_returns_only_failed(temp_perf_file):
    now = datetime.now().isoformat()
    metrics = [
        {"timestamp": now, "sql": "ok", "sql_hash": "a", "execution_time": 1.0, "success": True},
        {"timestamp": now, "sql": "bad", "sql_hash": "b", "execution_time": 1.0, "success": False},
    ]
    temp_perf_file.write_text(json.dumps(metrics), encoding="utf-8")
    failed = performance.get_failed_queries(limit=10)
    assert len(failed) == 1
    assert failed[0]["sql"] == "bad"


def test_get_performance_stats_non_empty(temp_perf_file):
    now = datetime.now().isoformat()
    metrics = [
        {"timestamp": now, "sql": "ok", "sql_hash": "a", "execution_time": 2.0, "success": True, "tokens_total": 10, "cache_hit_type": "sql", "model_used": "m1"},
        {"timestamp": now, "sql": "bad", "sql_hash": "b", "execution_time": 0.0, "success": False, "tokens_total": 5, "cache_hit_type": "none", "model_used": "m1"},
    ]
    temp_perf_file.write_text(json.dumps(metrics), encoding="utf-8")
    stats = performance.get_performance_stats(days=1)
    assert stats["total_queries"] == 2
    assert stats["failed_queries"] == 1
    assert stats["sql_cache_hits"] == 1


def test_clear_performance_metrics_handles_unlink_error(monkeypatch, temp_perf_file):
    temp_perf_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(performance.Path, "unlink", lambda *_a, **_k: (_ for _ in ()).throw(OSError("boom")))
    performance.clear_performance_metrics()
