"""Tests para validación de funciones SQL (Fase A)."""

import pytest

from src.schemas.database_schema import DatabaseSchema, TableSchema, ColumnSchema
from src.utils.exceptions import SQLValidationError
from src.validators.sql_validator import SQLValidator


@pytest.fixture
def mock_schema():
    """Schema de prueba con tablas básicas."""
    return DatabaseSchema(
        tables={
            "sales": TableSchema(
                name="sales",
                columns=[
                    ColumnSchema(name="id", type="INTEGER"),
                    ColumnSchema(name="revenue", type="DECIMAL"),
                    ColumnSchema(name="quantity", type="INTEGER"),
                    ColumnSchema(name="date", type="DATE"),
                ],
            ),
            "products": TableSchema(
                name="products",
                columns=[
                    ColumnSchema(name="id", type="INTEGER"),
                    ColumnSchema(name="name", type="VARCHAR"),
                    ColumnSchema(name="price", type="DECIMAL"),
                ],
            ),
        }
    )


def test_blocks_dangerous_function(mock_schema):
    """Verifica que funciones peligrosas sean bloqueadas."""
    validator = SQLValidator(mock_schema)
    
    # pg_sleep es una función peligrosa no permitida
    with pytest.raises(SQLValidationError) as exc_info:
        validator.validate_query("SELECT pg_sleep(10) FROM sales")
    
    assert "pg_sleep" in str(exc_info.value).lower()
    assert "no permitida" in str(exc_info.value).lower()


def test_allows_safe_aggregation_functions(mock_schema):
    """Verifica que funciones de agregación seguras sean permitidas."""
    validator = SQLValidator(mock_schema)
    
    # Estas funciones están en la whitelist
    queries = [
        "SELECT SUM(revenue), COUNT(*) FROM sales",
        "SELECT AVG(revenue), MIN(revenue), MAX(revenue) FROM sales",
        "SELECT COUNT(DISTINCT id) FROM sales",
    ]
    
    for query in queries:
        # No debería lanzar excepción
        validator.validate_query(query)


def test_allows_safe_string_functions(mock_schema):
    """Verifica que funciones de string seguras sean permitidas."""
    validator = SQLValidator(mock_schema)
    
    queries = [
        "SELECT UPPER(name), LOWER(name) FROM products",
        "SELECT TRIM(name), LENGTH(name) FROM products",
        "SELECT CONCAT(name, ' - Product') FROM products",
    ]
    
    for query in queries:
        validator.validate_query(query)


def test_allows_safe_date_functions(mock_schema):
    """Verifica que funciones de fecha seguras sean permitidas."""
    validator = SQLValidator(mock_schema)
    
    queries = [
        "SELECT DATE_TRUNC('month', date) FROM sales",
        "SELECT EXTRACT(YEAR FROM date) FROM sales",
        "SELECT NOW(), CURRENT_DATE",
    ]
    
    for query in queries:
        validator.validate_query(query)


def test_allows_safe_math_functions(mock_schema):
    """Verifica que funciones matemáticas seguras sean permitidas."""
    validator = SQLValidator(mock_schema)
    
    queries = [
        "SELECT ROUND(revenue, 2) FROM sales",
        "SELECT ABS(revenue), CEIL(revenue), FLOOR(revenue) FROM sales",
    ]
    
    for query in queries:
        validator.validate_query(query)


def test_allows_safe_conditional_functions(mock_schema):
    """Verifica que funciones condicionales seguras sean permitidas."""
    validator = SQLValidator(mock_schema)
    
    queries = [
        "SELECT COALESCE(revenue, 0) FROM sales",
        "SELECT NULLIF(quantity, 0) FROM sales",
        "SELECT CASE WHEN revenue > 100 THEN 'high' ELSE 'low' END FROM sales",
    ]
    
    for query in queries:
        validator.validate_query(query)


def test_blocks_system_functions(mock_schema):
    """Verifica que funciones de sistema sean bloqueadas."""
    validator = SQLValidator(mock_schema)
    
    dangerous_functions = [
        "SELECT pg_sleep(10) FROM sales",
        "SELECT pg_read_file('/etc/passwd') FROM sales",
        "SELECT version() FROM sales",
    ]
    
    for query in dangerous_functions:
        with pytest.raises(SQLValidationError):
            validator.validate_query(query)


def test_nested_allowed_functions(mock_schema):
    """Verifica que funciones anidadas permitidas funcionen."""
    validator = SQLValidator(mock_schema)
    
    query = "SELECT ROUND(AVG(revenue), 2) FROM sales"
    validator.validate_query(query)


def test_mixed_functions_one_dangerous(mock_schema):
    """Verifica que una función peligrosa en medio de funciones seguras sea detectada."""
    validator = SQLValidator(mock_schema)
    
    # pg_sleep es peligrosa, aunque SUM sea segura
    with pytest.raises(SQLValidationError) as exc_info:
        validator.validate_query("SELECT SUM(revenue), pg_sleep(1) FROM sales")
    
    assert "pg_sleep" in str(exc_info.value).lower()
