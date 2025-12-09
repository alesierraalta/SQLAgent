"""Descubrimiento automático de schema desde PostgreSQL."""

from typing import Dict, List

from sqlalchemy import Engine, inspect

from src.schemas.database_schema import (
    ColumnSchema,
    DatabaseSchema,
    TableSchema,
)
from src.utils.logger import logger


def discover_schema(engine: Engine, schema_name: str = "public") -> DatabaseSchema:
    """
    Descubre schema desde PostgreSQL automáticamente usando SQLAlchemy Inspector.
    
    Args:
        engine: SQLAlchemy Engine con conexión a la base de datos
        schema_name: Nombre del schema a descubrir (default: 'public')
        
    Returns:
        DatabaseSchema con todas las tablas y columnas descubiertas
        
    Raises:
        Exception: Si hay error al descubrir el schema
    """
    try:
        inspector = inspect(engine)
        tables: Dict[str, TableSchema] = {}
        
        # Obtener lista de tablas del schema
        table_names = inspector.get_table_names(schema=schema_name)
        
        if not table_names:
            logger.warning(f"No se encontraron tablas en el schema '{schema_name}'")
            return DatabaseSchema(tables={})
        
        logger.info(f"Descubriendo schema: {len(table_names)} tablas encontradas")
        
        for table_name in table_names:
            try:
                # Obtener columnas
                columns = []
                for col_info in inspector.get_columns(table_name, schema=schema_name):
                    # Convertir tipo SQLAlchemy a string
                    col_type = str(col_info['type'])
                    
                    columns.append(ColumnSchema(
                        name=col_info['name'],
                        type=col_type,
                        nullable=col_info.get('nullable', True),
                    ))
                
                # Obtener primary key
                pk_constraint = inspector.get_pk_constraint(table_name, schema=schema_name)
                primary_key = pk_constraint.get('constrained_columns', []) if pk_constraint else []
                
                # Obtener foreign keys
                foreign_keys: Dict[str, str] = {}
                for fk in inspector.get_foreign_keys(table_name, schema=schema_name):
                    # fk['constrained_columns'] es una lista, tomar el primero
                    # fk['referred_table'] y fk['referred_columns'] también son listas
                    if fk['constrained_columns'] and fk['referred_columns']:
                        constrained_col = fk['constrained_columns'][0]
                        referred_table = fk['referred_table']
                        referred_col = fk['referred_columns'][0]
                        foreign_keys[constrained_col] = f"{referred_table}.{referred_col}"
                
                # Crear TableSchema
                tables[table_name] = TableSchema(
                    name=table_name,
                    columns=columns,
                    primary_key=primary_key,
                    foreign_keys=foreign_keys,
                    description=f"Tabla descubierta automáticamente desde PostgreSQL",
                )
                
                logger.debug(
                    f"Tabla '{table_name}': {len(columns)} columnas, "
                    f"PK: {primary_key}, FKs: {len(foreign_keys)}"
                )
                
            except Exception as e:
                logger.warning(
                    f"Error al descubrir tabla '{table_name}': {e}. "
                    f"Omitiendo esta tabla."
                )
                continue
        
        logger.info(f"Schema descubierto exitosamente: {len(tables)} tablas")
        return DatabaseSchema(tables=tables)
        
    except Exception as e:
        logger.error(f"Error al descubrir schema: {e}")
        raise


def discover_schema_with_fallback(
    engine: Engine,
    fallback_schema: DatabaseSchema | None = None,
    schema_name: str = "public",
) -> DatabaseSchema:
    """
    Descubre schema con fallback a schema estático si falla.
    
    Args:
        engine: SQLAlchemy Engine
        fallback_schema: Schema estático a usar si discovery falla (opcional)
        schema_name: Nombre del schema a descubrir
        
    Returns:
        DatabaseSchema descubierto o fallback
    """
    try:
        return discover_schema(engine, schema_name)
    except Exception as e:
        logger.warning(
            f"Error al descubrir schema automáticamente: {e}. "
            f"Usando schema estático como fallback."
        )
        if fallback_schema:
            return fallback_schema
        # Si no hay fallback, retornar schema vacío
        return DatabaseSchema(tables={})
