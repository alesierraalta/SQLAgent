"""Tests adicionales para DatabaseSchema y carga de schema."""

import pytest

from src.schemas.database_schema import (
    ColumnSchema,
    DatabaseSchema,
    TableSchema,
    get_schema_for_prompt,
    get_schema_for_prompt_compact,
)


@pytest.fixture
def rich_schema():
    """Schema con descripción, PK y FK para cubrir ramas."""
    return DatabaseSchema(
        tables={
            "sales": TableSchema(
                name="sales",
                description="Tabla de ventas",
                columns=[
                    ColumnSchema(name="id", type="INTEGER", nullable=False),
                    ColumnSchema(name="product_id", type="INTEGER", nullable=False),
                    ColumnSchema(name="revenue", type="DECIMAL(10,2)", nullable=True),
                ],
                primary_key=["id"],
                foreign_keys={"product_id": "products.id"},
            ),
            "products": TableSchema(
                name="products",
                columns=[
                    ColumnSchema(name="id", type="INTEGER", nullable=False),
                    ColumnSchema(name="name", type="VARCHAR(200)", nullable=False),
                ],
                primary_key=["id"],
            ),
        }
    )


def test_get_allowed_columns_none_for_unknown_table(rich_schema):
    assert rich_schema.get_allowed_columns("unknown") is None


def test_validate_column_false_for_unknown_table(rich_schema):
    assert rich_schema.validate_column("unknown", "id") is False


def test_get_schema_for_prompt_includes_description_and_fks(rich_schema):
    formatted = get_schema_for_prompt(rich_schema)
    assert "Descripción: Tabla de ventas" in formatted
    assert "Foreign Keys:" in formatted
    assert "product_id -> products.id" in formatted


def test_get_schema_for_prompt_compact_includes_fk_marker(rich_schema):
    formatted = get_schema_for_prompt_compact(rich_schema)
    assert "sales(" in formatted
    assert "product_id INT FK?products.id" in formatted


def test_load_schema_internal_discovery_success(monkeypatch, rich_schema):
    from src.schemas import database_schema

    monkeypatch.setattr("src.utils.database.get_db_engine", lambda: object())
    monkeypatch.setattr(
        "src.utils.schema_discovery.discover_schema_with_fallback",
        lambda engine, fallback: rich_schema,
    )

    loaded = database_schema._load_schema_internal(use_discovery=True)
    assert loaded is rich_schema


def test_load_schema_internal_discovery_empty_falls_back(monkeypatch):
    from src.schemas import database_schema

    empty_schema = DatabaseSchema(tables={})
    monkeypatch.setattr("src.utils.database.get_db_engine", lambda: object())
    monkeypatch.setattr(
        "src.utils.schema_discovery.discover_schema_with_fallback",
        lambda engine, fallback: empty_schema,
    )

    loaded = database_schema._load_schema_internal(use_discovery=True)
    assert loaded.tables  # debe usar estático con tablas


def test_load_schema_internal_discovery_exception_falls_back(monkeypatch):
    from src.schemas import database_schema

    monkeypatch.setattr("src.utils.database.get_db_engine", lambda: object())

    def _raise(*args, **kwargs):
        raise Exception("boom")

    monkeypatch.setattr("src.utils.schema_discovery.discover_schema_with_fallback", _raise)

    loaded = database_schema._load_schema_internal(use_discovery=True)
    assert loaded.tables  # usa estático
