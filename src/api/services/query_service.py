"""Servicios para ejecutar consultas desde el API HTTP."""

from __future__ import annotations

import ast
import re
from typing import Any

from src.agents.query_explainer import explain_query
from src.agents.sql_agent import create_sql_agent, execute_query
from src.api.models import APIError, QueryRequest, QueryResponse
from src.schemas.database_schema import load_schema
from src.utils.database import get_db_engine
from src.utils.history import save_query
from src.utils.logger import logger


def _extract_column_names_from_sql(sql: str | None, num_cols: int) -> list[str] | None:
    """Extrae nombres de columnas del SELECT (best-effort)."""
    if not sql:
        return None

    sql_clean = sql.strip()
    if not sql_clean:
        return None

    try:
        sql_clean = re.sub(r"--.*?$", "", sql_clean, flags=re.MULTILINE)
        sql_clean = re.sub(r"/\\*.*?\\*/", "", sql_clean, flags=re.DOTALL)
        sql_clean = " ".join(sql_clean.split())

        select_match = re.search(r"SELECT\\s+(.+?)\\s+FROM", sql_clean, re.DOTALL | re.IGNORECASE)
        if not select_match:
            return None

        select_clause = select_match.group(1).strip()

        columns: list[str] = []
        current_col = ""
        paren_depth = 0
        in_quotes = False
        quote_char: str | None = None

        for char in select_clause:
            if char in ("'", '"') and not in_quotes:
                in_quotes = True
                quote_char = char
                current_col += char
                continue

            if quote_char is not None and char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current_col += char
                continue

            if in_quotes:
                current_col += char
                continue

            if char == "(":
                paren_depth += 1
                current_col += char
                continue

            if char == ")":
                paren_depth -= 1
                current_col += char
                continue

            if char == "," and paren_depth == 0:
                if current_col.strip():
                    columns.append(current_col.strip())
                current_col = ""
                continue

            current_col += char

        if current_col.strip():
            columns.append(current_col.strip())

        headers: list[str] = []
        for col in columns[:num_cols]:
            col_clean = col.strip()

            as_match = re.search(
                r"\\bAS\\s+[\"\\']?([a-zA-Z_][a-zA-Z0-9_]*)[\"\\']?",
                col_clean,
                re.IGNORECASE,
            )
            if as_match:
                headers.append(as_match.group(1))
                continue

            col_name_match = re.search(r"(?:[a-zA-Z_]+\\.)?([a-zA-Z_][a-zA-Z0-9_]*)", col_clean)
            if col_name_match:
                headers.append(col_name_match.group(1))
            else:
                headers.append(f"col_{len(headers) + 1}")

        return headers if len(headers) == num_cols else None

    except Exception:
        return None


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

    schema = load_schema()
    engine = get_db_engine()

    agent = create_sql_agent(engine, schema, question=question)

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

    schema = load_schema()
    engine = get_db_engine()

    agent = create_sql_agent(engine, schema, question=question_clean)
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
