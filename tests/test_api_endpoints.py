from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client() -> TestClient:
    from src.api.app import create_app

    with TestClient(create_app()) as client:
        yield client


def test_health_endpoint(api_client: TestClient) -> None:
    resp = api_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_query_endpoint_rejects_stream_flag(api_client: TestClient) -> None:
    resp = api_client.post("/api/v1/query", json={"question": "hola", "stream": True})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "stream_not_supported"


def test_schema_endpoint_compact(monkeypatch: pytest.MonkeyPatch, api_client: TestClient, sample_schema) -> None:
    import src.api.routers.schema as schema_router

    monkeypatch.setattr(schema_router, "load_schema", lambda force_refresh=False: sample_schema)

    resp = api_client.get("/api/v1/schema")
    assert resp.status_code == 200
    data = resp.json()
    assert data["compact"] is True
    assert data["table_count"] == 2
    assert data["returned_table_count"] == 2

    sales = next(t for t in data["tables"] if t["name"] == "sales")
    assert "primary_key" not in sales
    assert "foreign_keys" not in sales
    assert sales["columns"][0] == {"name": "id"}


def test_validate_sql_endpoint(monkeypatch: pytest.MonkeyPatch, api_client: TestClient, sample_schema) -> None:
    import src.api.routers.validate_sql as validate_sql_router

    monkeypatch.setattr(validate_sql_router, "load_schema", lambda force_refresh=False: sample_schema)

    ok = api_client.post("/api/v1/validate-sql", json={"sql": "SELECT id, revenue FROM sales"})
    assert ok.status_code == 200
    assert ok.json()["valid"] is True

    bad = api_client.post("/api/v1/validate-sql", json={"sql": "DROP TABLE sales"})
    assert bad.status_code == 200
    data = bad.json()
    assert data["valid"] is False
    assert data["errors"]


def test_history_endpoint_paginates(monkeypatch: pytest.MonkeyPatch, api_client: TestClient) -> None:
    import src.api.routers.history as history_router

    fake_history = [
        {
            "timestamp": "2025-01-02T00:00:00",
            "question": "Q2",
            "sql": "SELECT 2",
            "success": True,
            "response_preview": "ok2",
        },
        {
            "timestamp": "2025-01-01T00:00:00",
            "question": "Q1",
            "sql": "SELECT 1",
            "success": True,
            "response_preview": "ok1",
        },
    ]

    monkeypatch.setattr(history_router, "load_history", lambda limit=None: fake_history)

    resp = api_client.get("/api/v1/history?limit=1&offset=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["items"][0]["question"] == "Q1"


def test_clear_history_endpoint(monkeypatch: pytest.MonkeyPatch, api_client: TestClient) -> None:
    import src.api.routers.history as history_router

    called = {"value": False}

    def fake_clear_history() -> None:
        called["value"] = True

    monkeypatch.setattr(history_router, "clear_history", fake_clear_history)

    resp = api_client.post("/api/v1/history/clear")
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    assert called["value"] is True


def test_stats_endpoint(monkeypatch: pytest.MonkeyPatch, api_client: TestClient) -> None:
    import src.api.routers.stats as stats_router

    now = datetime.now().isoformat()
    fake_metrics = [
        {
            "timestamp": now,
            "sql": "SELECT 1",
            "sql_hash": "a",
            "execution_time": 10.0,
            "success": True,
        },
        {
            "timestamp": now,
            "sql": "SELECT 2",
            "sql_hash": "b",
            "execution_time": 1.0,
            "success": False,
        },
    ]

    monkeypatch.setattr(stats_router, "get_performance_stats", lambda days=7: {"total_queries": 2})
    monkeypatch.setattr(stats_router, "load_performance_metrics", lambda limit=None: fake_metrics)

    resp = api_client.get("/api/v1/stats?days=7&slow_threshold_seconds=5&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"]["total_queries"] == 2
    assert data["recent_metrics_count"] == 2
    assert len(data["slow_queries"]) == 1
    assert len(data["failed_queries"]) == 1
