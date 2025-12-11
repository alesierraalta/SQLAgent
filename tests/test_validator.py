"""Tests para el validador SQL."""

import pytest

from src.schemas.database_schema import ColumnSchema, DatabaseSchema, TableSchema
from src.utils.exceptions import (
    DangerousCommandError,
    InvalidColumnError,
    InvalidTableError,
    SQLValidationError,
)
from src.validators.sql_validator import SQLValidator


@pytest.fixture
def sample_schema():
    """Crea un schema de ejemplo para tests."""
    return DatabaseSchema(
        tables={
            "sales": TableSchema(
                name="sales",
                columns=[
                    ColumnSchema(name="id", type="INTEGER", nullable=False),
                    ColumnSchema(name="date", type="DATE", nullable=False),
                    ColumnSchema(name="revenue", type="DECIMAL(10,2)", nullable=False),
                    ColumnSchema(name="country", type="VARCHAR(100)", nullable=True),
                    ColumnSchema(name="product_id", type="INTEGER", nullable=True),
                    ColumnSchema(name="quantity", type="INTEGER", nullable=True),
                ],
                primary_key=["id"],
            ),
            "products": TableSchema(
                name="products",
                columns=[
                    ColumnSchema(name="id", type="INTEGER", nullable=False),
                    ColumnSchema(name="name", type="VARCHAR(200)", nullable=False),
                    ColumnSchema(name="category", type="VARCHAR(100)", nullable=True),
                ],
                primary_key=["id"],
            ),
        }
    )


@pytest.fixture
def validator(sample_schema):
    """Crea un validador con schema de ejemplo."""
    return SQLValidator(sample_schema)


def test_valid_simple_select(validator):
    """Test: SQL válido simple."""
    sql = "SELECT id, date, revenue FROM sales"
    # No debe lanzar excepción
    validator.validate_query(sql)


def test_valid_select_with_join(validator):
    """Test: SQL válido con JOIN."""
    sql = "SELECT s.id, p.name FROM sales s JOIN products p ON s.id = p.id"
    # No debe lanzar excepción
    validator.validate_query(sql)


def test_invalid_table(validator):
    """Test: SQL con tabla no permitida."""
    sql = "SELECT * FROM unauthorized_table"
    with pytest.raises(InvalidTableError) as exc_info:
        validator.validate_query(sql)
    assert "unauthorized_table" in str(exc_info.value)


def test_invalid_column(validator):
    """Test: SQL con columna no permitida."""
    sql = "SELECT unauthorized_column FROM sales"
    with pytest.raises(InvalidColumnError) as exc_info:
        validator.validate_query(sql)
    assert "unauthorized_column" in str(exc_info.value)


def test_dangerous_drop(validator):
    """Test: SQL con comando DROP."""
    sql = "DROP TABLE sales"
    with pytest.raises(DangerousCommandError) as exc_info:
        validator.validate_query(sql)
    assert "DROP" in str(exc_info.value)


def test_dangerous_insert(validator):
    """Test: SQL con comando INSERT."""
    sql = "INSERT INTO sales (id, date, revenue) VALUES (1, '2024-01-01', 100.0)"
    with pytest.raises(DangerousCommandError) as exc_info:
        validator.validate_query(sql)
    assert "INSERT" in str(exc_info.value)


def test_dangerous_update(validator):
    """Test: SQL con comando UPDATE."""
    sql = "UPDATE sales SET revenue = 200.0 WHERE id = 1"
    with pytest.raises(DangerousCommandError) as exc_info:
        validator.validate_query(sql)


def test_dangerous_delete(validator):
    """Test: SQL con comando DELETE."""
    sql = "DELETE FROM sales WHERE id = 1"
    with pytest.raises(DangerousCommandError) as exc_info:
        validator.validate_query(sql)


def test_subquery_valid(validator):
    """Test: SQL con subconsulta válida."""
    sql = "SELECT * FROM (SELECT id, revenue FROM sales) sub"
    # No debe lanzar excepción
    validator.validate_query(sql)


def test_subquery_invalid_table(validator):
    """Test: SQL con subconsulta que usa tabla inválida."""
    sql = "SELECT * FROM (SELECT * FROM unauthorized_table) sub"
    with pytest.raises(InvalidTableError):
        validator.validate_query(sql)


def test_cte_valid(validator):
    """Test: SQL con CTE válido."""
    sql = "WITH cte AS (SELECT id, revenue FROM sales) SELECT * FROM cte"
    # No debe lanzar excepción
    validator.validate_query(sql)


def test_extract_tables(validator):
    """Test: Extracción de tablas."""
    sql = "SELECT * FROM sales, products"
    tables = validator.extract_tables(sql)
    assert "sales" in tables
    assert "products" in tables


def test_extract_tables_with_join(validator):
    """Test: Extracción de tablas con JOIN."""
    sql = "SELECT * FROM sales s JOIN products p ON s.id = p.id"
    tables = validator.extract_tables(sql)
    assert "sales" in tables
    assert "products" in tables


def test_is_dangerous_command(validator):
    """Test: Detección de comandos peligrosos."""
    assert validator.is_dangerous_command("DROP TABLE sales")
    assert validator.is_dangerous_command("INSERT INTO sales VALUES (1)")
    assert not validator.is_dangerous_command("SELECT * FROM sales")


def test_extract_tables_with_alias_in_order_by(validator):
    """Test: No confundir alias de columnas en ORDER BY con tablas."""
    sql = "SELECT country, SUM(revenue) AS total_revenue FROM sales GROUP BY country ORDER BY total_revenue DESC"
    tables = validator.extract_tables(sql)
    assert "sales" in tables
    assert "total_revenue" not in tables
    assert "country" not in tables


def test_extract_tables_with_alias_in_group_by(validator):
    """Test: No confundir alias de columnas en GROUP BY con tablas."""
    sql = "SELECT category, COUNT(*) AS count FROM products GROUP BY category"
    tables = validator.extract_tables(sql)
    assert "products" in tables
    assert "category" not in tables
    assert "count" not in tables


def test_validate_query_with_alias_in_order_by(validator):
    """Test: Validar query con alias en ORDER BY no debe fallar."""
    sql = "SELECT country, SUM(revenue) AS total_revenue FROM sales GROUP BY country ORDER BY total_revenue DESC"
    # No debe lanzar InvalidTableError
    validator.validate_query(sql)


def test_validate_query_with_alias_in_select(validator):
    """Test: Validar query con alias simple en SELECT no debe fallar."""
    sql = "SELECT p.name AS product_name FROM products p"
    # No debe lanzar InvalidColumnError
    validator.validate_query(sql)


def test_validate_query_with_function_alias(validator):
    """Test: Validar query con función con alias no debe fallar."""
    sql = "SELECT SUM(s.revenue) AS total_revenue FROM sales s"
    # No debe lanzar InvalidColumnError
    validator.validate_query(sql)


def test_validate_query_with_multiple_aliases(validator):
    """Test: Validar query con múltiples aliases no debe fallar."""
    sql = "SELECT p.id AS product_id, p.name AS product_name, SUM(s.revenue) AS total_revenue FROM products p JOIN sales s ON p.id = s.product_id GROUP BY p.id, p.name"
    # No debe lanzar InvalidColumnError
    validator.validate_query(sql)


def test_validate_query_real_problem(validator):
    """Test: Validar la query del problema real."""
    sql = """SELECT p.id, p.name, SUM(s.revenue), SUM(s.quantity)
FROM sales s
JOIN products p ON s.product_id = p.id
GROUP BY p.id, p.name
ORDER BY SUM(s.revenue) DESC
LIMIT 10"""
    # No debe lanzar InvalidColumnError
    validator.validate_query(sql)


def test_rejects_multistatement(validator):
    """Test: Rechaza múltiples statements con ';'."""
    sql = "SELECT * FROM sales; DROP TABLE sales"
    with pytest.raises(SQLValidationError):
        validator.validate_query(sql)


def test_rejects_comments(validator):
    """Test: Rechaza comentarios en la query."""
    sql = "SELECT * FROM sales -- comentario"
    with pytest.raises(SQLValidationError):
        validator.validate_query(sql)


def test_rejects_dml_update(validator):
    """Test: Rechaza comando UPDATE."""
    sql = "UPDATE sales SET revenue = 0"
    with pytest.raises(DangerousCommandError):
        validator.validate_query(sql)


def test_cte_invalid_table(validator):
    """Test: CTE con tabla no permitida debe fallar."""
    sql = """
    WITH tmp AS (SELECT * FROM unauthorized_table)
    SELECT * FROM tmp
    """
    with pytest.raises(InvalidTableError):
        validator.validate_query(sql)


def test_date_functions_allowed(validator):
    """Test: funciones de fecha permitidas (MONTH, DATE_PART, TO_TIMESTAMP)."""
    sqls = [
        "SELECT EXTRACT(MONTH FROM date) FROM sales",
        "SELECT DATE_PART('month', date) FROM sales",
        "SELECT DATE_PART('week', date) FROM sales",
        "SELECT DATE_PART('quarter', date) FROM sales",
        "SELECT DATE_PART('day', date) FROM sales",
        "SELECT TO_TIMESTAMP(1700000000)",
    ]
    for sql in sqls:
        validator.validate_query(sql)


def test_parse_error(monkeypatch, validator):
    """Test: parse de sqlglot lanza error."""
    monkeypatch.setattr("sqlglot.parse", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("parse fail")))
    with pytest.raises(SQLValidationError):
        validator.validate_query("SELECT * FROM sales")


def test_empty_parse(monkeypatch, validator):
    """Test: sqlglot.parse retorna lista vacía."""
    monkeypatch.setattr("sqlglot.parse", lambda *args, **kwargs: [])
    with pytest.raises(SQLValidationError):
        validator.validate_query("SELECT * FROM sales")


def test_non_select_expression(validator):
    """Test: expresión no select_like debe fallar."""
    with pytest.raises(DangerousCommandError):
        validator.validate_query("VALUES (1)")


def test_is_dangerous_command_parse_fail(monkeypatch, validator):
    monkeypatch.setattr("sqlglot.parse", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("parse fail")))
    assert validator.is_dangerous_command("bad sql") is True


def test_is_dangerous_command_multi_statement(validator):
    assert validator.is_dangerous_command("SELECT 1; SELECT 2")
