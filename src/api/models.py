"""Modelos Pydantic del API HTTP."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Respuesta simple de healthcheck."""

    status: str = Field(default="ok", description="Estado del servicio")


class APIError(BaseModel):
    """Error estandarizado del API."""

    code: str = Field(description="Código corto del error")
    message: str = Field(description="Mensaje legible del error")


class QueryRequest(BaseModel):
    """Request para ejecutar una consulta en lenguaje natural."""

    question: str = Field(min_length=1, description="Pregunta en lenguaje natural")
    limit: int | None = Field(
        default=None,
        ge=1,
        le=10_000,
        description="Límite de filas a retornar/mostrar (best-effort)",
    )
    format: Literal["table", "json"] = Field(
        default="table",
        description="Preferencia de formato del cliente (el API responde JSON).",
    )
    explain: bool = Field(default=False, description="Incluye explicación del SQL")
    stream: bool = Field(
        default=False,
        description="Streaming (no soportado en /query; usar endpoint stream).",
    )


class QueryResponse(BaseModel):
    """Respuesta de una consulta."""

    success: bool = Field(description="Si la ejecución fue exitosa")
    response: str | None = Field(default=None, description="Respuesta raw del agente")
    columns: list[str] | None = Field(
        default=None,
        description="Columnas inferidas (si se pudo parsear respuesta tabular)",
    )
    rows: list[dict[str, Any]] | None = Field(
        default=None,
        description="Filas estructuradas (si se pudo parsear respuesta tabular)",
    )
    sql_generated: str | None = Field(default=None, description="SQL generado por el agente")
    explanation: str | None = Field(default=None, description="Explicación del SQL (opcional)")

    execution_time: float | None = Field(default=None, description="Tiempo de ejecución (segundos)")
    tokens_input: int | None = Field(default=None, description="Tokens de entrada (si disponible)")
    tokens_output: int | None = Field(default=None, description="Tokens de salida (si disponible)")
    tokens_total: int | None = Field(default=None, description="Tokens totales (si disponible)")
    cache_hit_type: str | None = Field(
        default=None,
        description="Tipo de cache hit: none|sql|semantic",
    )
    model_used: str | None = Field(default=None, description="Modelo usado (si disponible)")

    error: APIError | None = Field(default=None, description="Error si success=false")


class SchemaColumn(BaseModel):
    """Columna (para exponer schema vía API)."""

    name: str = Field(description="Nombre de la columna")
    type: str | None = Field(default=None, description="Tipo de dato SQL")
    nullable: bool | None = Field(default=None, description="Si permite NULL")


class SchemaTable(BaseModel):
    """Tabla (para exponer schema vía API)."""

    name: str = Field(description="Nombre de la tabla")
    description: str | None = Field(default=None, description="Descripción de la tabla")
    columns: list[SchemaColumn] = Field(description="Columnas de la tabla")
    primary_key: list[str] | None = Field(default=None, description="Primary key (si se incluye)")
    foreign_keys: dict[str, str] | None = Field(default=None, description="Foreign keys (si se incluye)")


class SchemaResponse(BaseModel):
    """Respuesta para GET /schema."""

    table_count: int = Field(description="Cantidad total de tablas disponibles")
    returned_table_count: int = Field(description="Cantidad de tablas retornadas")
    compact: bool = Field(description="Si la respuesta está compactada")
    tables: list[SchemaTable] = Field(description="Lista de tablas")


class ValidateSQLRequest(BaseModel):
    """Request para validar SQL manualmente."""

    sql: str = Field(min_length=1, description="SQL a validar (solo SELECT)")


class ValidateSQLResponse(BaseModel):
    """Respuesta de validación SQL."""

    valid: bool = Field(description="Si el SQL es válido/permitido")
    errors: list[str] = Field(default_factory=list, description="Errores de validación")
    tables: list[str] = Field(default_factory=list, description="Tablas detectadas (best-effort)")


class HistoryEntry(BaseModel):
    """Entrada individual de historial."""

    timestamp: str = Field(description="Timestamp ISO")
    question: str = Field(description="Pregunta en lenguaje natural")
    sql: str | None = Field(default=None, description="SQL generado (si aplica)")
    success: bool = Field(default=True, description="Si la ejecución fue exitosa")
    response_preview: str | None = Field(default=None, description="Preview de respuesta")
    cache_hit_type: str | None = Field(default=None, description="Tipo de cache hit (si se guardó)")
    model_used: str | None = Field(default=None, description="Modelo usado (si se guardó)")


class HistoryResponse(BaseModel):
    """Respuesta paginada de historial."""

    total: int = Field(description="Total de items (post-filtro)")
    items: list[HistoryEntry] = Field(description="Items de historial")


class ClearHistoryResponse(BaseModel):
    """Respuesta de borrado de historial."""

    success: bool = Field(description="Si el historial fue limpiado")
