"""Validador SQL estricto con whitelist y detección de comandos peligrosos."""

import re
from typing import List, Set

import sqlparse
from sqlparse.sql import Function, Identifier, IdentifierList, Parenthesis, Statement
from sqlparse.tokens import DML, Keyword

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
}

# Funciones SQL permitidas (whitelist)
ALLOWED_FUNCTIONS = {
    # Agregación
    "SUM", "COUNT", "AVG", "MIN", "MAX", "ARRAY_AGG", "STRING_AGG",
    # Manipulación de strings
    "UPPER", "LOWER", "TRIM", "LTRIM", "RTRIM", "LENGTH", "CONCAT", "SUBSTRING",
    # Fechas
    "DATE_TRUNC", "EXTRACT", "NOW", "CURRENT_DATE", "CURRENT_TIMESTAMP",
    # Condicionales
    "COALESCE", "NULLIF", "CASE", "GREATEST", "LEAST",
    # Matemáticas
    "ROUND", "ABS", "CEIL", "FLOOR",
    # Casting
    "CAST", "TO_CHAR", "TO_DATE", "TO_NUMBER",
}


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
        Valida una query SQL completa.

        Realiza las siguientes validaciones:
        1. Detecta comandos peligrosos
        2. Extrae y valida tablas
        3. Extrae y valida columnas
        4. Valida recursivamente subconsultas y CTEs

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

        # Normalizar SQL
        sql = sql.strip()

        # Parsear SQL
        try:
            parsed_statements = sqlparse.parse(sql)
            if not parsed_statements:
                raise SQLValidationError("No se pudo parsear la query SQL")

            # Validar cada statement
            for stmt in parsed_statements:
                self._validate_statement(stmt)

        except SQLValidationError:
            raise
        except Exception as e:
            raise SQLValidationError(f"Error al validar SQL: {str(e)}") from e

    def _validate_statement(self, stmt: Statement) -> None:
        """
        Valida un statement SQL parseado.

        Args:
            stmt: Statement parseado por sqlparse
        """
        # Detectar comando peligroso
        statement_type = stmt.get_type()
        if statement_type and statement_type.upper() in DANGEROUS_COMMANDS:
            raise DangerousCommandError(statement_type.upper(), str(stmt))

        # Solo permitir SELECT
        if statement_type and statement_type.upper() != "SELECT":
            if statement_type.upper() != "UNKNOWN":  # UNKNOWN puede ser CTE o subquery
                # Verificar si es realmente un SELECT (puede ser CTE)
                first_token = self._get_first_token(stmt)
                if first_token and first_token.upper() not in ("SELECT", "WITH"):
                    raise DangerousCommandError(statement_type.upper() or "UNKNOWN", str(stmt))

        # Extraer y validar tablas (pasar Statement directamente para evitar re-parsear)
        tables = self.extract_tables(stmt)
        for table in tables:
            if not self.schema.validate_table(table):
                allowed = self.schema.get_allowed_tables()
                raise InvalidTableError(table, allowed)

        # Validar funciones SQL permitidas (antes de columnas)

        self._validate_functions(stmt)



        # Extraer y validar columnas (solo para SELECT)
        if statement_type and statement_type.upper() == "SELECT":
            columns = self.extract_columns(str(stmt))
            for table, column_list in columns.items():
                if table and not self.schema.validate_table(table):
                    continue  # Ya validado arriba
                for column in column_list:
                    # Skip function names (they're validated separately)

                    if column.upper() in ALLOWED_FUNCTIONS or column == "*":

                        continue

                    

                    # Si table es None o "", buscar en todas las tablas
                    if not table:
                        # Buscar la columna en todas las tablas del schema
                        found = False
                        for schema_table_name, schema_table in self.schema.tables.items():
                            if self.schema.validate_column(schema_table_name, column):
                                found = True
                                break
                        if not found:
                            # Columna no encontrada en ninguna tabla
                            all_columns = []
                            for schema_table in self.schema.tables.values():
                                all_columns.extend([col.name for col in schema_table.columns])
                            raise InvalidColumnError(column, "", all_columns)
                    else:
                        # Validar columna en tabla específica
                        if not self.schema.validate_column(table, column):
                            allowed = self.schema.get_allowed_columns(table)
                            raise InvalidColumnError(column, table, allowed)


        # Validar subconsultas recursivamente
        self._validate_subqueries(stmt)

        # Validar CTEs
        self._validate_ctes(stmt)

    def _validate_functions(self, stmt: Statement) -> None:
        """Valida que solo se usen funciones SQL permitidas.
        
        Args:
            stmt: Statement parseado por sqlparse
            
        Raises:
            SQLValidationError: Si se encuentra una función no permitida
        """
        def check_token(token):
            """Recursively check tokens for functions."""
            if isinstance(token, Function):
                func_name = token.get_real_name()
                if func_name and func_name.upper() not in ALLOWED_FUNCTIONS:
                    raise SQLValidationError(
                        f"Función '{func_name}' no permitida. "
                        f"Funciones válidas: {', '.join(sorted(ALLOWED_FUNCTIONS))}"
                    )
            # Recursively check child tokens
            if hasattr(token, 'tokens'):
                for sub_token in token.tokens:
                    check_token(sub_token)
        
        check_token(stmt)

    def _get_first_token(self, stmt: Statement) -> str | None:
        """Obtiene el primer token no-whitespace del statement."""
        for token in stmt.tokens:
            if not token.is_whitespace and hasattr(token, "value"):
                return token.value.upper() if isinstance(token.value, str) else None
        return None

    def _validate_subqueries(self, stmt: Statement) -> None:
        """
        Valida subconsultas recursivamente.

        Args:
            stmt: Statement a validar
        """
        # Buscar subconsultas en el statement
        for token in stmt.tokens:
            if isinstance(token, Parenthesis):
                # Puede ser una subconsulta
                inner_sql = str(token).strip("()")
                if self._is_subquery(inner_sql):
                    inner_parsed = sqlparse.parse(inner_sql)
                    if inner_parsed:
                        self._validate_statement(inner_parsed[0])

    def _validate_ctes(self, stmt: Statement) -> None:
        """
        Valida Common Table Expressions (CTEs).

        Args:
            stmt: Statement a validar
        """
        sql_str = str(stmt)
        # Buscar WITH clause
        if re.search(r"\bWITH\s+", sql_str, re.IGNORECASE):
            # Extraer CTEs y validar cada uno
            cte_pattern = r"WITH\s+(\w+)\s+AS\s*\(([^)]+)\)"
            matches = re.finditer(cte_pattern, sql_str, re.IGNORECASE | re.DOTALL)
            for match in matches:
                cte_body = match.group(2)
                if self._is_subquery(cte_body):
                    cte_parsed = sqlparse.parse(cte_body)
                    if cte_parsed:
                        self._validate_statement(cte_parsed[0])

    def _is_subquery(self, sql: str) -> bool:
        """
        Determina si un SQL es una subconsulta SELECT.

        Args:
            sql: SQL a verificar

        Returns:
            True si es una subconsulta SELECT
        """
        sql_upper = sql.strip().upper()
        return sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")

    def extract_tables(self, sql: str | Statement) -> List[str]:
        """
        Extrae nombres de tablas de una query SQL.

        Args:
            sql: Query SQL (string) o Statement parseado

        Returns:
            Lista de nombres de tablas encontradas
        """
        tables: Set[str] = set()
        
        # Aceptar Statement directamente o parsear string
        if isinstance(sql, Statement):
            stmt = sql
        else:
            parsed = sqlparse.parse(sql)
            if not parsed:
                return []
            stmt = parsed[0]

        # Extraer tablas SOLO de FROM y JOIN (no de ORDER BY, GROUP BY, etc.)
        from_seen = False
        order_by_seen = False
        group_by_seen = False
        
        for token in stmt.tokens:
            # Detectar FROM
            if token.ttype is Keyword and token.value.upper() == "FROM":
                from_seen = True
                continue
            
            # Detectar ORDER BY y GROUP BY para detener extracción
            if token.ttype is Keyword:
                token_upper = token.value.upper() if hasattr(token, "value") else ""
                if token_upper in ("ORDER", "GROUP"):
                    # Marcar que encontramos ORDER BY o GROUP BY
                    if token_upper == "ORDER":
                        order_by_seen = True
                    elif token_upper == "GROUP":
                        group_by_seen = True
                    break  # Detener extracción de tablas
            
            # Solo extraer tablas si estamos en la sección FROM (antes de ORDER/GROUP BY)
            if from_seen and not order_by_seen and not group_by_seen:
                if isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        table_name = self._extract_table_name(identifier)
                        if table_name:
                            tables.add(table_name)
                elif isinstance(token, Identifier):
                    table_name = self._extract_table_name(token)
                    if table_name:
                        tables.add(table_name)
                elif token.ttype is Keyword and token.value.upper() in ("WHERE", "HAVING", "LIMIT"):
                    # Detener en WHERE, HAVING, LIMIT también
                    break

        # Extraer tablas de JOINs
        for token in stmt.tokens:
            if token.ttype is Keyword and token.value.upper() in ("JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN"):
                # El siguiente token debería ser la tabla
                idx = stmt.tokens.index(token)
                if idx + 1 < len(stmt.tokens):
                    next_token = stmt.tokens[idx + 1]
                    if isinstance(next_token, Identifier):
                        table_name = self._extract_table_name(next_token)
                        if table_name:
                            tables.add(table_name)

        # Filtrar nombres que son columnas o alias, pero no tablas (validación post-extracción)
        filtered_tables = []
        for table in tables:
            # Verificar si el nombre existe como tabla en el schema
            if self.schema.validate_table(table):
                filtered_tables.append(table)
            else:
                # Verificar si es una columna (falso positivo)
                is_column = False
                for schema_table in self.schema.tables.values():
                    if any(col.name.lower() == table.lower() for col in schema_table.columns):
                        is_column = True
                        break
                
                # Si no es columna ni tabla, probablemente es un alias o nombre de CTE
                # Solo agregar si podría ser una tabla de subconsulta/CTE (nombres comunes de alias no se agregan)
                # Nombres que terminan en patrones comunes de alias se ignoran
                if not is_column:
                    # Ignorar nombres que parecen alias comunes (sin punto, no es tabla, no es columna)
                    # Pero permitir nombres que podrían ser CTEs o subconsultas
                    # Por ahora, ser más estricto: solo agregar si realmente podría ser una tabla
                    # En la práctica, si no es tabla ni columna del schema, es probablemente un alias
                    pass  # No agregar alias como tablas

        return filtered_tables

    def _extract_table_name(self, identifier: Identifier) -> str | None:
        """
        Extrae el nombre real de una tabla de un Identifier.

        Args:
            identifier: Identifier de sqlparse

        Returns:
            Nombre de la tabla o None
        """
        if identifier.is_wildcard():
            return None

        # Obtener nombre real (sin alias)
        real_name = identifier.get_real_name()
        if real_name:
            # Remover comillas y normalizar
            return real_name.strip('"').strip("'").lower()

        return None

    def extract_columns(self, sql: str) -> dict[str, List[str]]:
        """
        Extrae nombres de columnas REALES de una query SQL (ignora alias y funciones).

        Args:
            sql: Query SQL

        Returns:
            Diccionario {table_name: [column_names]} o {None: [column_names]} si no hay tabla
        """
        columns: dict[str, List[str]] = {}
        parsed = sqlparse.parse(sql)

        if not parsed:
            return columns

        stmt = parsed[0]

        # Extraer columnas SOLO del SELECT (antes de FROM)
        # NO extraer de ORDER BY, GROUP BY, HAVING (pueden contener alias)
        select_seen = False
        from_seen = False
        for token in stmt.tokens:
            # Detectar SELECT
            if token.ttype is DML and token.value.upper() == "SELECT":
                select_seen = True
                continue
            
            # Detectar FROM y detener extracción
            if token.ttype is Keyword and token.value.upper() == "FROM":
                from_seen = True
                break
            
            # Si estamos en SELECT pero aún no en FROM, extraer columnas
            if select_seen and not from_seen:
                # Detener si encontramos GROUP BY, ORDER BY, HAVING, WHERE antes de FROM
                if token.ttype is Keyword and token.value.upper() in ("GROUP", "ORDER", "HAVING", "WHERE"):
                    break
                
                if isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        # Extraer solo columnas reales (ignorar alias)
                        self._extract_real_columns_from_identifier(identifier, columns)
                elif isinstance(token, Function):
                    # Manejar funciones agregadas: extraer columnas de dentro, no la función
                    self._extract_columns_from_function(token, columns)
                elif isinstance(token, Identifier):
                    # Extraer columna real (ignorar si es alias)
                    self._extract_real_columns_from_identifier(token, columns)

        return columns

    def _extract_real_columns_from_identifier(self, identifier: Identifier, columns: dict[str, List[str]]) -> None:
        """
        Extrae columnas REALES de un Identifier, ignorando alias.
        
        Args:
            identifier: Identifier de sqlparse
            columns: Diccionario donde agregar columnas
        """
        # Si es una función, extraer columnas de dentro (no el alias de la función)
        if isinstance(identifier, Function):
            self._extract_columns_from_function(identifier, columns)
            return
        
        # Verificar si el identifier tiene alias pero no tiene nombre real
        # (esto ocurre cuando solo hay un alias sin columna real, como en funciones con alias)
        if hasattr(identifier, 'get_alias') and hasattr(identifier, 'get_real_name'):
            alias = identifier.get_alias()
            real_name = identifier.get_real_name()
            # Si tiene alias pero no tiene nombre real, es solo un alias (no una columna real)
            if alias and not real_name:
                return  # Ignorar alias puro, no es una columna real
        
        # Extraer información de columna (ya usa get_real_name() internamente)
        col_info = self._extract_column_info(identifier)
        if col_info:
            table, column = col_info
            # Solo agregar si no es un wildcard
            if column == "*":
                return
            # Agregar columnas reales para validación posterior
            if table:
                # Columna con tabla especificada
                if table not in columns:
                    columns[table] = []
                if column not in columns[table]:
                    columns[table].append(column)
            else:
                # Columna sin tabla - agregar para validación
                # (se validará contra todas las tablas del schema)
                if None not in columns:
                    columns[None] = []
                if column not in columns[None]:
                    columns[None].append(column)
    
    def _is_real_column(self, column_name: str) -> bool:
        """
        Verifica si un nombre es una columna real (existe en el schema).
        
        Args:
            column_name: Nombre a verificar
            
        Returns:
            True si existe en alguna tabla del schema
        """
        # Verificar si existe en alguna tabla del schema
        for schema_table in self.schema.tables.values():
            if any(col.name.lower() == column_name.lower() for col in schema_table.columns):
                return True
        return False
    
    def _extract_columns_from_function(self, function: Function, columns: dict[str, List[str]]) -> None:
        """
        Extrae columnas de dentro de una función agregada (SUM, COUNT, etc.).

        Args:
            function: Function token de sqlparse
            columns: Diccionario de columnas donde agregar resultados
        """
        # Iterar sobre los tokens dentro de la función para encontrar Identifiers
        for token in function.tokens:
            if isinstance(token, Identifier):
                col_info = self._extract_column_info(token)
                if col_info:
                    table, column = col_info
                    if table not in columns:
                        columns[table] = []
                    if column not in columns[table]:
                        columns[table].append(column)
            elif isinstance(token, Function):
                # Funciones anidadas
                self._extract_columns_from_function(token, columns)
            elif isinstance(token, IdentifierList):
                # Múltiples columnas en la función
                for identifier in token.get_identifiers():
                    if isinstance(identifier, Identifier):
                        col_info = self._extract_column_info(identifier)
                        if col_info:
                            table, column = col_info
                            if table not in columns:
                                columns[table] = []
                            if column not in columns[table]:
                                columns[table].append(column)

    def _extract_column_info(self, identifier: Identifier) -> tuple[str | None, str] | None:
        """
        Extrae información de columna (tabla y nombre) de un Identifier.
        Usa get_real_name() para obtener el nombre real, ignorando aliases.

        Args:
            identifier: Identifier de sqlparse

        Returns:
            Tupla (table_name, column_name) o None
        """
        if hasattr(identifier, 'is_wildcard') and identifier.is_wildcard():
            return None, "*"

        # Obtener nombre real (ignora alias si existe)
        if not hasattr(identifier, 'get_real_name'):
            return None
        full_name = identifier.get_real_name()
        if not full_name:
            return None

        # Separar tabla y columna si hay punto
        if "." in full_name:
            parts = full_name.split(".", 1)
            table = parts[0].strip('"').strip("'").lower()
            column = parts[1].strip('"').strip("'").lower()
            return table, column
        else:
            # Solo columna, sin tabla
            column = full_name.strip('"').strip("'").lower()
            return None, column

    def is_dangerous_command(self, sql: str) -> bool:
        """
        Verifica si un SQL contiene comandos peligrosos.

        Args:
            sql: Query SQL a verificar

        Returns:
            True si contiene comandos peligrosos
        """
        sql_upper = sql.strip().upper()
        for cmd in DANGEROUS_COMMANDS:
            # Buscar comando al inicio o después de punto y coma
            pattern = rf"^\s*{cmd}\b|\s*;\s*{cmd}\b"
            if re.search(pattern, sql_upper):
                return True
        return False
