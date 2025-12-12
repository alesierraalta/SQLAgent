"""Endpoints de schema."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.api.models import SchemaColumn, SchemaResponse, SchemaTable
from src.schemas.database_schema import load_schema

router = APIRouter(tags=["schema"])


@router.get("/schema", response_model=SchemaResponse, response_model_exclude_none=True)
def schema_endpoint(
    compact: bool = Query(default=True, description="Si True, omite detalles (types/keys) para reducir payload."),
    max_tables: int | None = Query(default=None, ge=1, le=500, description="Máximo de tablas a retornar."),
    force_refresh: bool = Query(default=False, description="Si True, fuerza recarga de schema ignorando cache."),
) -> SchemaResponse:
    """Devuelve el schema de la base (desde discovery o fallback estático)."""
    schema = load_schema(force_refresh=force_refresh)

    tables = sorted(schema.tables.values(), key=lambda t: t.name)
    total_tables = len(tables)

    if max_tables is not None:
        tables = tables[:max_tables]

    response_tables: list[SchemaTable] = []
    for table in tables:
        if compact:
            columns = [SchemaColumn(name=col.name) for col in table.columns]
            response_tables.append(
                SchemaTable(
                    name=table.name,
                    description=table.description or None,
                    columns=columns,
                )
            )
        else:
            columns = [SchemaColumn(name=col.name, type=col.type, nullable=col.nullable) for col in table.columns]
            response_tables.append(
                SchemaTable(
                    name=table.name,
                    description=table.description or None,
                    columns=columns,
                    primary_key=table.primary_key or None,
                    foreign_keys=table.foreign_keys or None,
                )
            )

    return SchemaResponse(
        table_count=total_tables,
        returned_table_count=len(response_tables),
        compact=compact,
        tables=response_tables,
    )
