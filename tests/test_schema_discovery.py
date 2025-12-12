"""Tests unitarios para schema_discovery sin conexión real."""

import pytest

from src.schemas.database_schema import DatabaseSchema
from src.utils import schema_discovery


class FakeInspector:
    def __init__(self, table_names, columns_map=None, pk_map=None, fk_map=None, raise_on=None):
        self._table_names = table_names
        self._columns_map = columns_map or {}
        self._pk_map = pk_map or {}
        self._fk_map = fk_map or {}
        self._raise_on = set(raise_on or [])

    def get_table_names(self, schema=None):
        return self._table_names

    def get_columns(self, table_name, schema=None):
        if table_name in self._raise_on:
            raise Exception("boom")
        return self._columns_map.get(table_name, [])

    def get_pk_constraint(self, table_name, schema=None):
        return self._pk_map.get(table_name)

    def get_foreign_keys(self, table_name, schema=None):
        return self._fk_map.get(table_name, [])


def test_discover_schema_returns_empty_when_no_tables(monkeypatch):
    fake = FakeInspector(table_names=[])
    monkeypatch.setattr(schema_discovery, "inspect", lambda engine: fake)

    schema = schema_discovery.discover_schema(engine=object())
    assert schema.tables == {}


def test_discover_schema_builds_tables_with_pk_fk(monkeypatch):
    fake = FakeInspector(
        table_names=["sales"],
        columns_map={
            "sales": [
                {"name": "id", "type": "INTEGER", "nullable": False},
                {"name": "product_id", "type": "INTEGER", "nullable": True},
            ]
        },
        pk_map={"sales": {"constrained_columns": ["id"]}},
        fk_map={
            "sales": [
                {
                    "constrained_columns": ["product_id"],
                    "referred_table": "products",
                    "referred_columns": ["id"],
                }
            ]
        },
    )
    monkeypatch.setattr(schema_discovery, "inspect", lambda engine: fake)

    schema = schema_discovery.discover_schema(engine=object())
    assert "sales" in schema.tables
    table = schema.tables["sales"]
    assert table.primary_key == ["id"]
    assert table.foreign_keys["product_id"] == "products.id"


def test_discover_schema_skips_tables_on_error(monkeypatch):
    fake = FakeInspector(
        table_names=["good", "bad"],
        columns_map={"good": [{"name": "id", "type": "INTEGER"}]},
        raise_on=["bad"],
    )
    monkeypatch.setattr(schema_discovery, "inspect", lambda engine: fake)

    schema = schema_discovery.discover_schema(engine=object())
    assert "good" in schema.tables
    assert "bad" not in schema.tables


def test_discover_schema_raises_on_inspector_failure(monkeypatch):
    monkeypatch.setattr(schema_discovery, "inspect", lambda engine: (_ for _ in ()).throw(Exception("fail")))
    with pytest.raises(Exception):
        schema_discovery.discover_schema(engine=object())


def test_discover_schema_with_fallback_returns_fallback(monkeypatch):
    fallback = DatabaseSchema(tables={})
    monkeypatch.setattr(schema_discovery, "discover_schema", lambda *a, **k: (_ for _ in ()).throw(Exception("x")))
    result = schema_discovery.discover_schema_with_fallback(engine=object(), fallback_schema=fallback)
    assert result is fallback


def test_discover_schema_with_fallback_returns_empty_when_no_fallback(monkeypatch):
    monkeypatch.setattr(schema_discovery, "discover_schema", lambda *a, **k: (_ for _ in ()).throw(Exception("x")))
    result = schema_discovery.discover_schema_with_fallback(engine=object(), fallback_schema=None)
    assert result.tables == {}
