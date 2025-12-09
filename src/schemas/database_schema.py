"""Definición del schema estático de la base de datos usando Pydantic."""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    """Schema de una columna de tabla."""

    name: str = Field(..., description="Nombre de la columna")
    type: str = Field(..., description="Tipo de dato SQL (ej: VARCHAR, INTEGER, DATE)")
    nullable: bool = Field(default=True, description="Si la columna permite valores NULL")


class TableSchema(BaseModel):
    """Schema de una tabla de la base de datos."""

    name: str = Field(..., description="Nombre de la tabla")
    columns: List[ColumnSchema] = Field(..., description="Lista de columnas de la tabla")
    primary_key: List[str] = Field(default_factory=list, description="Columnas que forman la primary key")
    foreign_keys: Dict[str, str] = Field(
        default_factory=dict,
        description="Foreign keys: {column_name: 'referenced_table.referenced_column'}",
    )
    description: str = Field(default="", description="Descripción de la tabla y su propósito")


class DatabaseSchema(BaseModel):
    """Schema completo de la base de datos."""

    tables: Dict[str, TableSchema] = Field(..., description="Diccionario de tablas indexado por nombre")

    def get_table(self, table_name: str) -> TableSchema | None:
        """
        Obtiene el schema de una tabla por nombre.

        Args:
            table_name: Nombre de la tabla

        Returns:
            TableSchema si existe, None en caso contrario
        """
        return self.tables.get(table_name.lower())

    def get_allowed_tables(self) -> List[str]:
        """
        Retorna lista de todas las tablas permitidas.

        Returns:
            Lista de nombres de tablas
        """
        return list(self.tables.keys())

    def get_allowed_columns(self, table_name: str) -> List[str] | None:
        """
        Retorna lista de columnas permitidas para una tabla.

        Args:
            table_name: Nombre de la tabla

        Returns:
            Lista de nombres de columnas o None si la tabla no existe
        """
        table = self.get_table(table_name)
        if table is None:
            return None
        return [col.name for col in table.columns]

    def validate_table(self, table_name: str) -> bool:
        """
        Valida si una tabla está permitida en el schema.

        Args:
            table_name: Nombre de la tabla a validar

        Returns:
            True si la tabla está permitida, False en caso contrario
        """
        return table_name.lower() in self.tables

    def validate_column(self, table_name: str, column_name: str) -> bool:
        """
        Valida si una columna está permitida en una tabla.

        Args:
            table_name: Nombre de la tabla
            column_name: Nombre de la columna

        Returns:
            True si la columna está permitida, False en caso contrario
        """
        table = self.get_table(table_name)
        if table is None:
            return False
        return any(col.name.lower() == column_name.lower() for col in table.columns)


@dataclass
class CachedSchema:
    """Schema cacheado con TTL (Time To Live)."""
    
    schema: DatabaseSchema
    fetched_at: datetime
    ttl_seconds: int = 300  # Default: 5 minutos
    
    def is_expired(self) -> bool:
        """
        Verifica si el cache ha expirado.
        
        Returns:
            True si el cache expiró, False en caso contrario
        """
        return datetime.now() > self.fetched_at + timedelta(seconds=self.ttl_seconds)


# Cache global del schema con TTL
_schema_cache: Optional[CachedSchema] = None


def _load_static_schema() -> DatabaseSchema:
    """
    Carga el schema estático de ejemplo (fallback).
    
    Returns:
        DatabaseSchema estático de ejemplo
    """
    return DatabaseSchema(
        tables={
            "sales": TableSchema(
                name="sales",
                description="Tabla de ventas con información de transacciones",
                columns=[
                    ColumnSchema(name="id", type="INTEGER", nullable=False),
                    ColumnSchema(name="date", type="DATE", nullable=False),
                    ColumnSchema(name="country", type="VARCHAR(100)", nullable=False),
                    ColumnSchema(name="product_id", type="INTEGER", nullable=False),
                    ColumnSchema(name="revenue", type="DECIMAL(10,2)", nullable=False),
                    ColumnSchema(name="quantity", type="INTEGER", nullable=False),
                ],
                primary_key=["id"],
                foreign_keys={"product_id": "products.id"},
            ),
            "products": TableSchema(
                name="products",
                description="Tabla de productos del catálogo",
                columns=[
                    ColumnSchema(name="id", type="INTEGER", nullable=False),
                    ColumnSchema(name="name", type="VARCHAR(200)", nullable=False),
                    ColumnSchema(name="category", type="VARCHAR(100)", nullable=True),
                    ColumnSchema(name="price", type="DECIMAL(10,2)", nullable=False),
                ],
                primary_key=["id"],
            ),
        }
    )


def load_schema(use_discovery: bool | None = None, force_refresh: bool = False) -> DatabaseSchema:
    """
    Carga el schema de la base de datos con cache TTL.
    
    Por defecto, intenta descubrir el schema automáticamente desde PostgreSQL.
    Si falla o si use_discovery=False, usa el schema estático como fallback.
    
    El schema se cachea en memoria con TTL para evitar recargas innecesarias.
    El cache expira automáticamente después del tiempo configurado en SCHEMA_TTL_SECONDS.
    
    Args:
        use_discovery: Si True, fuerza discovery. Si False, fuerza estático.
                      Si None, usa variable de entorno SCHEMA_DISCOVERY o intenta discovery.
        force_refresh: Si True, fuerza recarga del schema ignorando cache
    
    Returns:
        DatabaseSchema con todas las tablas y columnas definidas
    """
    global _schema_cache
    
    # Obtener TTL de variable de entorno
    ttl = int(os.getenv("SCHEMA_TTL_SECONDS", "300"))
    
    # Usar cache si existe, no expiró y no se fuerza refresh
    if _schema_cache and not _schema_cache.is_expired() and not force_refresh:
        from src.utils.logger import logger
        logger.debug(f"Usando schema cacheado (expira en {(_schema_cache.fetched_at + timedelta(seconds=_schema_cache.ttl_seconds) - datetime.now()).seconds}s)")
        return _schema_cache.schema
    
    # Cargar schema (discovery o estático)
    schema = _load_schema_internal(use_discovery)
    
    # Cachear con TTL
    _schema_cache = CachedSchema(
        schema=schema,
        fetched_at=datetime.now(),
        ttl_seconds=ttl
    )
    
    from src.utils.logger import logger
    logger.info(f"Schema cargado y cacheado (TTL: {ttl}s, tablas: {len(schema.tables)})")
    
    return schema


def _load_schema_internal(use_discovery: bool | None = None) -> DatabaseSchema:
    """
    Carga el schema internamente (sin cache).
    
    Args:
        use_discovery: Si usar discovery automático o schema estático
        
    Returns:
        DatabaseSchema cargado
    """
    # Importar aquí para evitar circular import
    from src.utils.database import get_db_engine
    from src.utils.logger import logger
    from src.utils.schema_discovery import discover_schema_with_fallback
    
    # Determinar si usar discovery
    if use_discovery is None:
        # Verificar variable de entorno
        env_discovery = os.getenv("SCHEMA_DISCOVERY", "true").lower()
        use_discovery = env_discovery in ("true", "1", "yes")
    
    if use_discovery:
        try:
            # Intentar descubrir schema automáticamente
            engine = get_db_engine()
            fallback_schema = _load_static_schema()
            schema = discover_schema_with_fallback(engine, fallback_schema)
            
            if schema.tables:
                logger.info(
                    f"Schema cargado desde discovery: {len(schema.tables)} tablas"
                )
                return schema
            else:
                logger.warning("Schema discovery retornó vacío, usando estático")
                return fallback_schema
                
        except Exception as e:
            logger.warning(
                f"Error al descubrir schema automáticamente: {e}. "
                f"Usando schema estático."
            )
            return _load_static_schema()
    else:
        # Usar schema estático
        logger.info("Usando schema estático (SCHEMA_DISCOVERY=false)")
        return _load_static_schema()


def invalidate_schema_cache() -> None:
    """
    Invalida el cache del schema, forzando recarga en próxima llamada.
    
    Útil cuando se sabe que el schema de la base de datos ha cambiado
    (ej: después de migraciones, ALTER TABLE, etc.)
    """
    global _schema_cache
    _schema_cache = None
    
    from src.utils.logger import logger
    logger.info("Cache de schema invalidado manualmente")


def get_schema_for_prompt(schema: DatabaseSchema) -> str:
    """
    Formatea el schema para incluir en el prompt del agente LangChain.

    Crea una descripción legible del schema que el LLM puede usar para
    generar queries SQL correctas.

    Args:
        schema: DatabaseSchema a formatear

    Returns:
        String formateado con la descripción del schema
    """
    lines = ["=== SCHEMA DE BASE DE DATOS ===\n"]

    for table_name, table in schema.tables.items():
        lines.append(f"Tabla: {table_name}")
        if table.description:
            lines.append(f"  Descripción: {table.description}")

        lines.append("  Columnas:")
        for col in table.columns:
            nullable_str = "NULL" if col.nullable else "NOT NULL"
            lines.append(f"    - {col.name} ({col.type}) {nullable_str}")

        if table.primary_key:
            lines.append(f"  Primary Key: {', '.join(table.primary_key)}")

        if table.foreign_keys:
            lines.append("  Foreign Keys:")
            for col, ref in table.foreign_keys.items():
                lines.append(f"    - {col} -> {ref}")

        lines.append("")

    return "\n".join(lines)


def get_schema_for_prompt_compact(schema: DatabaseSchema) -> str:
    """
    Formatea el schema en formato compacto para reducir tokens.
    
    Formato compacto: "sales(id INT PK, date DATE, country VARCHAR, product_id INT FK?products.id, revenue DECIMAL, quantity INT)"
    Reduce tokens en 60-70% comparado con formato detallado.
    
    Args:
        schema: DatabaseSchema a formatear
        
    Returns:
        String formateado con schema compacto
    """
    lines = ["=== SCHEMA (COMPACTO) ===\n"]
    
    for table_name, table in schema.tables.items():
        # Construir lista de columnas en formato compacto
        col_parts = []
        for col in table.columns:
            # Tipo básico (simplificar tipos largos)
            type_simple = col.type.split('(')[0] if '(' in col.type else col.type
            type_simple = type_simple.upper()
            
            # Abreviaciones comunes
            type_map = {
                "VARCHAR": "STR",
                "DECIMAL": "DEC",
                "INTEGER": "INT",
                "TIMESTAMP": "TS",
                "BOOLEAN": "BOOL"
            }
            type_short = type_map.get(type_simple, type_simple)
            
            col_str = f"{col.name} {type_short}"
            
            # Agregar PK si es primary key
            if col.name in table.primary_key:
                col_str += " PK"
            
            # Agregar FK si tiene foreign key
            if col.name in table.foreign_keys:
                ref = table.foreign_keys[col.name]
                col_str += f" FK?{ref}"
            
            # Agregar NOT NULL si aplica
            if not col.nullable:
                col_str += " NOT NULL"
            
            col_parts.append(col_str)
        
        # Formato: "tabla(col1, col2, ...)"
        table_line = f"{table_name}({', '.join(col_parts)})"
        lines.append(table_line)
    
    return "\n".join(lines)
