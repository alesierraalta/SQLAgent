"""Sistema de cache para resultados de queries SQL."""

import hashlib
import os
import sqlparse
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Optional

from src.utils.logger import logger
from src.utils.persistent_cache import get_cache_backend

# FASE C: Cache persistente con múltiples backends
_cache_backend = None
_cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # Default: 1 hora


def _get_cache() -> Any:
    """Obtiene la instancia del backend de cache (lazy initialization)."""
    global _cache_backend
    if _cache_backend is None:
        _cache_backend = get_cache_backend()
    return _cache_backend


def normalize_sql(sql: str) -> str:
    """
    Normaliza SQL para cache (elimina diferencias de formato).
    
    Normaliza:
    - Espacios múltiples
    - Mayúsculas/minúsculas en keywords
    - Orden de whitespace
    
    Args:
        sql: Query SQL a normalizar
        
    Returns:
        SQL normalizado
    """
    try:
        # Parsear y reformatear SQL para normalización
        parsed = sqlparse.parse(sql)
        if not parsed:
            return sql.strip().upper()
        
        # Formatear con estilo consistente
        normalized = sqlparse.format(
            str(parsed[0]),
            reindent=True,
            keyword_case='upper',
            identifier_case='lower',
            strip_comments=True,
        )
        return normalized.strip()
    except Exception as e:
        logger.warning(f"Error al normalizar SQL para cache: {e}. Usando hash directo.")
        # Fallback: normalización simple
        return sql.strip().upper()


def get_sql_hash(sql: str) -> str:
    """
    Genera hash MD5 de SQL normalizado para usar como key de cache.
    
    Args:
        sql: Query SQL
        
    Returns:
        Hash MD5 hexadecimal del SQL normalizado
    """
    normalized = normalize_sql(sql)
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def get_cached_result(sql: str) -> Optional[str]:
    """
    Obtiene resultado cacheado para una query SQL.
    
    Args:
        sql: Query SQL
        
    Returns:
        Resultado cacheado o None si no existe o expiró
    """
    cache = _get_cache()
    sql_hash = get_sql_hash(sql)
    
    cache_entry = cache.get(sql_hash)
    
    if cache_entry is None:
        return None
    
    # Verificar si expiró
    if datetime.now() > cache_entry['expires_at']:
        # Eliminar entrada expirada
        cache.delete(sql_hash)
        logger.debug(f"Cache expirado para query: {sql[:50]}...")
        return None
    
    logger.debug(f"Cache hit para query: {sql[:50]}...")
    return cache_entry['result']


def set_cached_result(sql: str, result: str, ttl_seconds: Optional[int] = None) -> None:
    """
    Guarda resultado en cache.
    
    Args:
        sql: Query SQL
        result: Resultado a cachear
        ttl_seconds: Tiempo de vida en segundos (None = usar default)
    """
    cache = _get_cache()
    sql_hash = get_sql_hash(sql)
    ttl = ttl_seconds or _cache_ttl_seconds
    
    cache_entry = {
        'result': result,
        'expires_at': datetime.now() + timedelta(seconds=ttl),
        'cached_at': datetime.now(),
        'sql_preview': sql[:100],  # Para debugging
    }
    
    cache.set(sql_hash, cache_entry)
    logger.debug(f"Resultado cacheado para query: {sql[:50]}... (TTL: {ttl}s)")


def clear_cache() -> None:
    """Limpia todo el cache."""
    cache = _get_cache()
    cache.clear()
    logger.info("Cache limpiado")


def invalidate_cache(sql: Optional[str] = None) -> None:
    """
    Invalida cache para una query específica o todo el cache.
    
    Args:
        sql: Query SQL a invalidar (None = invalidar todo)
    """
    if sql is None:
        clear_cache()
        return
    
    cache = _get_cache()
    sql_hash = get_sql_hash(sql)
    cache.delete(sql_hash)
    logger.debug(f"Cache invalidado para query: {sql[:50]}...")


def get_cache_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas del cache.
    
    Returns:
        Diccionario con estadísticas (tamaño, entradas, etc.)
    """
    cache = _get_cache()
    stats = cache.get_stats()
    stats['ttl_seconds'] = _cache_ttl_seconds
    return stats


def cleanup_expired_cache() -> None:
    """Elimina entradas expiradas del cache."""
    cache = _get_cache()
    
    # FileCache tiene método cleanup_expired, otros backends lo hacen automáticamente
    if hasattr(cache, 'cleanup_expired'):
        removed = cache.cleanup_expired()
        if removed > 0:
            logger.debug(f"Limpiadas {removed} entradas expiradas del cache")
    else:
        logger.debug("Backend de cache maneja expiración automáticamente")
