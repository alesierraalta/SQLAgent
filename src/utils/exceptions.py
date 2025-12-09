"""Excepciones personalizadas para el sistema LLM-DW."""


class LLMDWError(Exception):
    """Excepción base para todos los errores del sistema."""

    def __init__(self, message: str, details: dict | None = None):
        """
        Inicializa la excepción.

        Args:
            message: Mensaje de error descriptivo
            details: Diccionario opcional con detalles adicionales del error
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SQLValidationError(LLMDWError):
    """Error en validación SQL."""

    pass


class InvalidTableError(SQLValidationError):
    """Tabla no permitida en el schema."""

    def __init__(self, table_name: str, allowed_tables: list[str] | None = None):
        """
        Inicializa el error de tabla inválida.

        Args:
            table_name: Nombre de la tabla no permitida
            allowed_tables: Lista de tablas permitidas (opcional)
        """
        message = f"Tabla '{table_name}' no está permitida en el schema."
        if allowed_tables:
            message += f" Tablas permitidas: {', '.join(allowed_tables)}"
        super().__init__(message, {"table_name": table_name, "allowed_tables": allowed_tables})


class InvalidColumnError(SQLValidationError):
    """Columna no permitida en el schema."""

    def __init__(self, column_name: str, table_name: str, allowed_columns: list[str] | None = None):
        """
        Inicializa el error de columna inválida.

        Args:
            column_name: Nombre de la columna no permitida
            table_name: Nombre de la tabla
            allowed_columns: Lista de columnas permitidas (opcional)
        """
        message = f"Columna '{column_name}' no está permitida en la tabla '{table_name}'."
        if allowed_columns:
            message += f" Columnas permitidas: {', '.join(allowed_columns)}"
        super().__init__(
            message,
            {
                "column_name": column_name,
                "table_name": table_name,
                "allowed_columns": allowed_columns,
            },
        )


class DangerousCommandError(SQLValidationError):
    """Comando peligroso detectado (DROP, INSERT, UPDATE, DELETE, etc.)."""

    def __init__(self, command: str, sql: str | None = None):
        """
        Inicializa el error de comando peligroso.

        Args:
            command: Tipo de comando peligroso detectado
            sql: SQL completo que contiene el comando (opcional)
        """
        message = f"Comando peligroso '{command}' detectado. Solo se permiten consultas SELECT."
        super().__init__(message, {"command": command, "sql": sql})


class DatabaseConnectionError(LLMDWError):
    """Error de conexión a la base de datos."""

    def __init__(self, message: str, database_url: str | None = None):
        """
        Inicializa el error de conexión.

        Args:
            message: Mensaje de error descriptivo
            database_url: URL de la base de datos (sin credenciales) (opcional)
        """
        super().__init__(message, {"database_url": database_url})


class LLMError(LLMDWError):
    """Error en la API de LLM."""

    def __init__(self, message: str, error_code: str | None = None, api_response: dict | None = None):
        """
        Inicializa el error de LLM.

        Args:
            message: Mensaje de error descriptivo
            error_code: Código de error de la API (opcional)
            api_response: Respuesta completa de la API (opcional)
        """
        super().__init__(message, {"error_code": error_code, "api_response": api_response})
