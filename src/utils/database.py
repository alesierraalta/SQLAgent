"""Gestión de conexiones a la base de datos con connection pooling."""

import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import QueuePool

from src.utils.exceptions import DatabaseConnectionError

# Cargar variables de entorno
load_dotenv()

# Engine global (singleton pattern)
_engine: Engine | None = None


def get_db_engine() -> Engine:
    """
    Obtiene o crea el engine de SQLAlchemy con connection pooling.

    Configuración del pool:
    - pool_size=5: Mantiene 5 conexiones persistentes
    - max_overflow=10: Permite hasta 10 conexiones adicionales
    - pool_pre_ping=True: Verifica que las conexiones estén vivas antes de usarlas
    - pool_recycle=3600: Recicla conexiones después de 1 hora

    Returns:
        Engine de SQLAlchemy configurado

    Raises:
        DatabaseConnectionError: Si no se puede crear el engine o la URL es inválida
    """
    global _engine

    if _engine is not None:
        return _engine

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise DatabaseConnectionError(
            "DATABASE_URL no está configurada en las variables de entorno.",
        )

    try:
        _engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verifica conexiones antes de usarlas
            pool_recycle=3600,  # Recicla conexiones después de 1 hora
            echo=False,  # Cambiar a True para debug SQL
        )
        return _engine
    except Exception as e:
        # Ocultar credenciales del error
        safe_url = _sanitize_url(database_url)
        raise DatabaseConnectionError(
            f"Error al crear engine de base de datos: {str(e)}",
            database_url=safe_url,
        ) from e


def _sanitize_url(url: str) -> str:
    """
    Sanitiza la URL de la base de datos ocultando credenciales.

    Args:
        url: URL completa de la base de datos

    Returns:
        URL sanitizada sin credenciales
    """
    try:
        # Formato: postgresql://user:password@host:port/dbname
        if "@" in url:
            parts = url.split("@")
            if len(parts) == 2:
                protocol_part = parts[0]
                if "://" in protocol_part:
                    protocol = protocol_part.split("://")[0]
                    return f"{protocol}://***:***@{parts[1]}"
        return "***"
    except Exception:
        return "***"


@contextmanager
def get_db_connection() -> Generator:
    """
    Context manager para obtener una conexión de la pool.

    Uso:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT 1"))
            print(result.fetchone())

    Yields:
        Connection de SQLAlchemy

    Raises:
        DatabaseConnectionError: Si no se puede obtener la conexión
    """
    engine = get_db_engine()
    try:
        with engine.connect() as conn:
            yield conn
    except Exception as e:
        safe_url = _sanitize_url(str(engine.url))
        raise DatabaseConnectionError(
            f"Error al obtener conexión de la base de datos: {str(e)}",
            database_url=safe_url,
        ) from e


def test_connection() -> bool:
    """
    Prueba la conexión a la base de datos.

    Returns:
        True si la conexión es exitosa, False en caso contrario
    """
    try:
        with get_db_connection() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def dispose_engine() -> None:
    """
    Cierra todas las conexiones del pool y elimina el engine.

    Útil para cleanup en tests o shutdown de la aplicación.
    """
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
