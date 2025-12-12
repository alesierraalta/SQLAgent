"""Endpoints de estadísticas."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query

from src.utils.performance import get_performance_stats, load_performance_metrics

router = APIRouter(tags=["stats"])


def _filter_metrics_by_days(metrics: list[dict[str, Any]], days: int) -> list[dict[str, Any]]:
    cutoff = datetime.now() - timedelta(days=days)
    filtered: list[dict[str, Any]] = []
    for metric in metrics:
        ts_raw = metric.get("timestamp")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            continue
        if ts >= cutoff:
            filtered.append(metric)
    return filtered


@router.get("/stats")
def stats_endpoint(
    days: int = Query(default=7, ge=1, le=365, description="Ventana de tiempo (días) para agregados."),
    slow_threshold_seconds: float = Query(
        default=5.0,
        ge=0.0,
        le=600.0,
        description="Threshold para considerar una query lenta.",
    ),
    limit: int = Query(default=10, ge=1, le=100, description="Máximo de items por lista."),
) -> dict[str, Any]:
    """Devuelve métricas agregadas y lists de queries lentas/fallidas."""
    stats = get_performance_stats(days=days)

    all_metrics = load_performance_metrics(limit=None)
    recent_metrics = _filter_metrics_by_days(all_metrics, days=days)

    slow_queries = [
        m
        for m in recent_metrics
        if m.get("success", False)
        and m.get("execution_time", 0) >= slow_threshold_seconds
        and str(m.get("sql", "")).strip()
    ]
    slow_queries.sort(key=lambda m: m.get("execution_time", 0), reverse=True)

    failed_queries = [m for m in recent_metrics if not m.get("success", True)]
    failed_queries.sort(key=lambda m: m.get("timestamp", ""), reverse=True)

    patterns: dict[str, dict[str, Any]] = {}
    for metric in recent_metrics:
        sql = str(metric.get("sql", "")).strip()
        if not sql:
            continue
        sql_hash = str(metric.get("sql_hash", "unknown"))
        if sql_hash not in patterns:
            patterns[sql_hash] = {
                "sql_hash": sql_hash,
                "sql_preview": sql[:100],
                "count": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "success_count": 0,
                "fail_count": 0,
            }
        pattern = patterns[sql_hash]
        pattern["count"] += 1
        pattern["total_time"] += float(metric.get("execution_time", 0) or 0.0)
        if metric.get("success", False):
            pattern["success_count"] += 1
        else:
            pattern["fail_count"] += 1

    pattern_list = []
    for pattern in patterns.values():
        if pattern["count"] > 0:
            pattern["avg_time"] = pattern["total_time"] / pattern["count"]
            pattern_list.append(pattern)
    pattern_list.sort(key=lambda p: p["count"], reverse=True)

    return {
        "stats": stats,
        "recent_metrics_count": len(recent_metrics),
        "slow_queries": slow_queries[:limit],
        "failed_queries": failed_queries[:limit],
        "patterns": pattern_list[:limit],
    }
