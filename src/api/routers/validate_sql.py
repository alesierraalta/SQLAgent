"""Endpoints para validar SQL manualmente."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.models import ValidateSQLRequest, ValidateSQLResponse
from src.schemas.database_schema import load_schema
from src.utils.exceptions import SQLValidationError
from src.validators.sql_validator import SQLValidator

router = APIRouter(tags=["validate-sql"])


@router.post("/validate-sql", response_model=ValidateSQLResponse)
def validate_sql_endpoint(request: ValidateSQLRequest) -> ValidateSQLResponse:
    """Valida SQL contra el schema permitido (solo SELECT)."""
    sql = request.sql.strip()
    if not sql:
        return ValidateSQLResponse(valid=False, errors=["SQL vacío o inválido."])

    schema = load_schema()
    validator = SQLValidator(schema)

    tables: list[str] = []
    try:
        tables = validator.extract_tables(sql)
    except Exception:
        tables = []

    try:
        validator.validate_query(sql)
        return ValidateSQLResponse(valid=True, tables=tables)
    except SQLValidationError as e:
        return ValidateSQLResponse(valid=False, errors=[str(e)], tables=tables)
    except Exception as e:
        return ValidateSQLResponse(valid=False, errors=[f"Error inesperado: {e}"], tables=tables)

