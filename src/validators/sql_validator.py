import re
from typing import Dict, Set

import sqlglot
from sqlglot import exp

from src.schemas.database_schema import DatabaseSchema
from src.utils.exceptions import (
    DangerousCommandError,
    InvalidColumnError,
    InvalidTableError,
    SQLValidationError,
)

# Comandos SQL peligrosos que no están permitidos
DANGEROUS_COMMANDS = {
    "DROP",
    "INSERT",
    "UPDATE",
    "DELETE",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "EXEC",
    "EXECUTE",
    "COPY",
    "ANALYZE",
    "VACUUM",
    "COMMENT",
    "CALL",
    "DO",
    "SET",
    "SHOW",
    "LOCK",
    "CHECKPOINT",
    "REFRESH",
}

# Funciones SQL permitidas (whitelist)
ALLOWED_FUNCTIONS = {
    # Agregación
    "SUM",
    "COUNT",
    "AVG",
    "MIN",
    "MAX",
    "ARRAY_AGG",
    "STRING_AGG",
    # Manipulación de strings
    "UPPER",
    "LOWER",
    "TRIM",
    "LTRIM",
    "RTRIM",
    "LENGTH",
    "CONCAT",
    "SUBSTRING",
    # Fechas
    "DATE_TRUNC",
    "EXTRACT",
    "YEAR",
    "NOW",
    "CURRENT_DATE",
    "CURRENT_TIMESTAMP",
    # Condicionales
    "COALESCE",
    "NULLIF",
    "CASE",
    "GREATEST",
    "LEAST",
    # Matemáticas
    "ROUND",
    "ABS",
    "CEIL",
    "FLOOR",
    # Casting
    "CAST",
    "TO_CHAR",
    "TO_DATE",
    "TO_NUMBER",
}

# Expresiones explícitamente prohibidas (AST)
DANGEROUS_EXPRESSION_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Alter,
    exp.Drop,
    exp.Grant,
    exp.Revoke,
    exp.Command,  # cubre COPY/SET/SHOW/etc.
)


class SQLValidator:
    """Validador SQL con whitelist estricto y detección de comandos peligrosos."""

    def __init__(self, schema: DatabaseSchema):
        """
        Inicializa el validador con un schema.

        Args:
            schema: DatabaseSchema con las tablas y columnas permitidas
        """
        self.schema = schema

    def validate_query(self, sql: str) -> None:
        """
        Valida una query SQL completa (solo SELECT/CTE/UNION) usando sqlglot AST.

        Args:
            sql: Query SQL a validar

        Raises:
            DangerousCommandError: Si se detecta un comando peligroso
            InvalidTableError: Si se usa una tabla no permitida
            InvalidColumnError: Si se usa una columna no permitida
            SQLValidationError: Para otros errores de validación
        """
        if not sql or not sql.strip():
            raise SQLValidationError("Query SQL vacía o inválida")

        sql = sql.strip()
        self._reject_comments_and_semicolons(sql)

        try:
            parsed = sqlglot.parse(sql, read="postgres")
        except Exception as e:
            raise SQLValidationError(f"No se pudo parsear la query SQL: {e}") from e

        if not parsed:
            raise SQLValidationError("No se pudo parsear la query SQL")
        if len(parsed) != 1:
            raise SQLValidationError("Solo se permite un statement SQL")

        expression = parsed[0]
        self._validate_expression(expression)

    # ---------------------- helpers ---------------------- #
    def _reject_comments_and_semicolons(self, sql: str) -> None:
        if ";" in sql:
            raise SQLValidationError("No se permiten múltiples statements ni ';'")
        if re.search(r"(--|/\\*|#)", sql):
            raise SQLValidationError("No se permiten comentarios en la query")

    def _is_select_like(self, expression: exp.Expression) -> bool:
        return isinstance(expression, (exp.Select, exp.Union, exp.With, exp.Subquery))

    def _validate_expression(self, expression: exp.Expression) -> None:
        # Rechazar comandos explícitos peligrosos por tipo AST
        for node in expression.walk():
            if isinstance(node, DANGEROUS_EXPRESSION_TYPES):
                raise DangerousCommandError(node.key.upper(), str(node))

        # Solo se permiten SELECT/CTE/UNION
        if not self._is_select_like(expression):
            raise DangerousCommandError(expression.key.upper(), str(expression))

        # Validar CTEs recursivamente
        cte_names: Set[str] = set()
        for cte in expression.find_all(exp.CTE):
            if cte.alias:
                cte_names.add(cte.alias)
            if cte.this:
                self._validate_expression(cte.this)

        # Construir mapa alias->tabla real (solo tablas reales, no CTEs)
        alias_map = self._build_table_alias_map(expression)
        alias_names = {alias.alias for alias in expression.find_all(exp.Alias) if alias.alias}
        # Validar tablas (incluye FROM/JOIN y subqueries)
        self._validate_tables_and_aliases(expression, cte_names)
        # Validar funciones
        self._validate_functions(expression)
        # Validar columnas
        self._validate_columns(expression, alias_map, cte_names, alias_names)

    def _build_table_alias_map(self, expression: exp.Expression) -> Dict[str, str]:
        alias_map: Dict[str, str] = {}
        for table in expression.find_all(exp.Table):
            table_name = table.name
            if not table_name:
                continue
            if table.alias:
                alias_map[table.alias] = table_name
        return alias_map

    def _validate_tables_and_aliases(self, expression: exp.Expression, cte_names: Set[str]) -> None:
        for table in expression.find_all(exp.Table):
            table_name = table.name
            if not table_name:
                continue
            # CTEs se consideran permitidos (se validan aparte)
            if table_name in cte_names:
                continue
            if table_name.upper() in DANGEROUS_COMMANDS:
                raise DangerousCommandError(table_name.upper(), str(expression))
            if not self.schema.validate_table(table_name):
                allowed = self.schema.get_allowed_tables()
                raise InvalidTableError(table_name, allowed)

    def _validate_functions(self, expression: exp.Expression) -> None:
        for func in expression.find_all(exp.Func):
            func_name = func.name
            if not func_name:
                continue
            if func_name == "*":
                continue
            if func_name.upper() not in ALLOWED_FUNCTIONS:
                raise SQLValidationError(
                    f"Función '{func_name}' no permitida. "
                    f"Funciones válidas: {', '.join(sorted(ALLOWED_FUNCTIONS))}"
                )

    def _validate_columns(
        self,
        expression: exp.Expression,
        alias_map: Dict[str, str],
        cte_names: Set[str],
        select_aliases: Set[str],
    ) -> None:
        for column in expression.find_all(exp.Column):
            column_name = column.name
            if not column_name or column_name == "*":
                continue
            if column_name in select_aliases:
                continue

            table_ref = column.table
            if table_ref:
                # Resolver alias -> tabla real
                real_table = alias_map.get(table_ref, table_ref)
                if real_table in cte_names:
                    # No podemos validar columnas de CTE sin esquema; permitir
                    continue
                if not self.schema.validate_table(real_table):
                    allowed_tables = self.schema.get_allowed_tables()
                    raise InvalidTableError(real_table, allowed_tables)
                if not self.schema.validate_column(real_table, column_name):
                    allowed_columns = self.schema.get_allowed_columns(real_table)
                    raise InvalidColumnError(column_name, real_table, allowed_columns)
            else:
                # Sin tabla: validar contra todas las tablas del schema
                found = False
                for schema_table_name in self.schema.tables.keys():
                    if self.schema.validate_column(schema_table_name, column_name):
                        found = True
                        break
                if not found:
                    all_columns = []
                    for schema_table in self.schema.tables.values():
                        all_columns.extend([col.name for col in schema_table.columns])
                    raise InvalidColumnError(column_name, "", all_columns)

    # --------- compatibilidad con tests existentes --------- #
    def extract_tables(self, sql: str | exp.Expression) -> list[str]:
        """
        Extrae nombres de tablas usando sqlglot (solo tablas reales; CTEs incluidas).
        """
        expression: exp.Expression
        if isinstance(sql, exp.Expression):
            expression = sql
        else:
            parsed = sqlglot.parse(sql, read="postgres")
            if not parsed:
                return []
            expression = parsed[0]

        tables: Set[str] = set()
        for table in expression.find_all(exp.Table):
            if table.name:
                tables.add(table.name)
        return list(tables)

    def is_dangerous_command(self, sql: str) -> bool:
        """
        Detecta si el SQL contiene un comando peligroso.
        """
        try:
            parsed = sqlglot.parse(sql, read="postgres")
        except Exception:
            return True

        if len(parsed) != 1:
            return True

        expr = parsed[0]
        for node in expr.walk():
            if isinstance(node, DANGEROUS_EXPRESSION_TYPES):
                return True
            # También revisar palabras clave explícitas
            if isinstance(node, exp.Identifier) and node.name.upper() in DANGEROUS_COMMANDS:
                return True
        return False
