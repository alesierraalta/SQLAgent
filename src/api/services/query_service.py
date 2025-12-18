"""Servicios para ejecutar consultas desde el API HTTP."""

from __future__ import annotations

import ast
import re
from typing import Any

import sqlglot
from sqlglot import exp

from src.agents.query_explainer import explain_query
from src.agents.sql_agent import create_sql_agent, execute_query
from src.api.models import APIError, QueryRequest, QueryResponse
from src.schemas.database_schema import load_schema
from src.utils.database import get_db_engine
from src.utils.history import save_query
from src.utils.logger import logger
from src.utils.semantic_cache import initialize_semantic_cache


def _extract_column_names_from_sql(sql: str | None, num_cols: int) -> list[str] | None:
    """Extrae nombres de columnas del SELECT (best-effort) usando sqlglot."""
    if not sql:
        return None

    try:
        expression = sqlglot.parse_one(sql, read="postgres")
    except Exception:
        return None

    if not isinstance(expression, exp.Select):
        return None

    headers: list[str] = []
    for select_item in expression.expressions:
        if isinstance(select_item, exp.Alias):
            headers.append(select_item.alias_or_name)
        elif isinstance(select_item, exp.Column):
            headers.append(select_item.name)
        elif isinstance(select_item, exp.Cast): # Handle CAST(col as type)
            if isinstance(select_item.this, exp.Column):
                headers.append(select_item.this.name)
            else:
                # Fallback for complex expressions in CAST
                headers.append(select_item.sqlgen())
        elif hasattr(select_item, 'name'): # For functions, etc.
            headers.append(select_item.name)
        else:
            headers.append(select_item.sqlgen()) # Fallback for complex expressions

        if len(headers) == num_cols:
            break

    # Clean up headers (remove quotes from column names if present)
    cleaned_headers = [re.sub(r'^"|"$', '', h).strip() for h in headers]

    return cleaned_headers if len(cleaned_headers) == num_cols else None


def _parse_rows_from_response(
    response: str | None, sql_generated: str | None, limit: int | None
) -> tuple[list[str] | None, list[dict[str, Any]] | None]:
    """Convierte una respuesta del agente a filas/columnas (best-effort)."""
    if not response:
        return None, None

    normalized = response.strip()
    if not normalized:
        return None, None

    if not (normalized.startswith("[") or normalized.startswith("{")):
        return None, None

    try:
        parsed: Any = ast.literal_eval(normalized)
    except (ValueError, SyntaxError):
        # Algunos resultados vienen con saltos de línea/espacios raros.
        cleaned = re.sub(r"\\s+", " ", normalized)
        cleaned = cleaned.replace(" ,", ",").replace(", ", ",")
        try:
            parsed = ast.literal_eval(cleaned)
        except (ValueError, SyntaxError):
            return None, None

    # Lista de tuplas/listas: filas tabulares
    if isinstance(parsed, list) and parsed:
        if isinstance(parsed[0], (tuple, list)):
            rows_list = [list(row) for row in parsed]
            if not rows_list:
                return None, None

            num_cols = len(rows_list[0])
            headers = _extract_column_names_from_sql(sql_generated, num_cols) or [
                f"col_{i + 1}" for i in range(num_cols)
            ]

            row_dicts: list[dict[str, Any]] = []
            for row in rows_list:
                row_dicts.append({headers[i]: (row[i] if i < len(row) else None) for i in range(num_cols)})

            if limit is not None:
                row_dicts = row_dicts[:limit]

            return headers, row_dicts

        # Lista de dicts: ya estructurado
        if isinstance(parsed[0], dict):
            row_dicts = [dict(row) for row in parsed if isinstance(row, dict)]
            if limit is not None:
                row_dicts = row_dicts[:limit]

            # Columnas como unión de keys (orden estable por aparición).
            columns: list[str] = []
            seen: set[str] = set()
            for row in row_dicts:
                for key in row.keys():
                    if key not in seen:
                        seen.add(key)
                        columns.append(str(key))
            return columns or None, row_dicts or None

    return None, None


def _build_query_response(
    *,
    question: str,
    engine: Any,
    execute_result: str | dict[str, Any],
    limit: int | None,
    explain: bool,
) -> QueryResponse:
    """Construye QueryResponse a partir del resultado de execute_query()."""
    if not isinstance(execute_result, dict):
        response_text = str(execute_result)
        save_query(question=question, sql=None, response=response_text, success=not response_text.startswith("Error"))
        return QueryResponse(success=not response_text.startswith("Error"), response=response_text)

    response_text = execute_result.get("response")
    sql_generated = execute_result.get("sql_generated")
    success = bool(execute_result.get("success"))

    try:
        save_query(
            question=question,
            sql=sql_generated,
            response=response_text,
            success=success,
            cache_hit_type=execute_result.get("cache_hit_type"),
            model_used=execute_result.get("model_used"),
        )
    except Exception as e:
        logger.warning(f"No se pudo guardar historial: {e}")

    columns, rows = _parse_rows_from_response(response_text, sql_generated, limit)

    explanation: str | None = None
    if explain and sql_generated:
        explanation = explain_query(sql_generated, engine)

    error: APIError | None = None
    if not success:
        message = response_text or "Error al ejecutar la query."
        error = APIError(code="query_failed", message=message)

    return QueryResponse(
        success=success,
        response=response_text,
        columns=columns,
        rows=rows,
        sql_generated=sql_generated,
        explanation=explanation,
        execution_time=execute_result.get("execution_time"),
        tokens_input=execute_result.get("tokens_input"),
        tokens_output=execute_result.get("tokens_output"),
        tokens_total=execute_result.get("tokens_total"),
        cache_hit_type=execute_result.get("cache_hit_type"),
        model_used=execute_result.get("model_used"),
        error=error,
    )


def run_query(request: QueryRequest) -> QueryResponse:
    """Ejecuta una consulta (single-shot) reusando el core existente."""
    question = request.question.strip()
    if not question:
        return QueryResponse(
            success=False,
            error=APIError(code="invalid_question", message="La pregunta no puede estar vacía."),
        )

    if request.stream:
        return QueryResponse(
            success=False,
            error=APIError(
                code="stream_not_supported",
                message="Streaming no soportado en /query. Usa el endpoint de streaming.",
            ),
        )

    # Pre-cargar embeddings (semantic cache) como en el CLI, para evitar cold-start en la primera query.
    try:
        initialize_semantic_cache()
    except Exception as e:
        logger.debug(f"No se pudo pre-cargar modelo de embeddings: {e}")

    schema = load_schema()
    engine = get_db_engine()

    # Igual que el CLI: crear agente sin pasar `question` para evitar inicializar el clasificador ML en cada query.
    agent = create_sql_agent(engine, schema)

    result = execute_query(agent, question, return_metadata=True, stream=False)
    return _build_query_response(
        question=question,
        engine=engine,
        execute_result=result,
        limit=request.limit,
        explain=request.explain,
    )


def run_query_stream(
    *,
    question: str,
    limit: int | None,
    explain: bool,
    stream_callback: Any | None,
) -> QueryResponse:
    """Ejecuta una consulta en modo streaming (para SSE) y retorna el resultado final."""
    question_clean = question.strip()
    if not question_clean:
        return QueryResponse(
            success=False,
            error=APIError(code="invalid_question", message="La pregunta no puede estar vacía."),
        )

    # Pre-cargar embeddings (semantic cache) como en el CLI, para evitar cold-start en la primera query.
    try:
        initialize_semantic_cache()
    except Exception as e:
        logger.debug(f"No se pudo pre-cargar modelo de embeddings: {e}")

    schema = load_schema()
    engine = get_db_engine()

    agent = create_sql_agent(engine, schema)
    result = execute_query(
        agent,
        question_clean,
        return_metadata=True,
        stream=True,
        stream_callback=stream_callback,
    )

    return _build_query_response(
        question=question_clean,
        engine=engine,
        execute_result=result,
        limit=limit,
        explain=explain,
    )
