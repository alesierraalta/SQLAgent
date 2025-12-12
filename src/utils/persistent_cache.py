"""Sistema de cache persistente con múltiples backends (Fase C)."""

import json
import os
import pickle
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from src.utils.logger import logger


class CacheBackend(ABC):
    """Interfaz abstracta para backends de cache."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un valor del cache.
        
        Args:
            key: Clave del cache
            
        Returns:
            Dict con 'result', 'expires_at', 'cached_at', 'sql_preview' o None
        """
        pass  # pragma: no cover
    
    @abstractmethod
    def set(self, key: str, value: Dict[str, Any]) -> None:
        """
        Guarda un valor en el cache.
        
        Args:
            key: Clave del cache
            value: Dict con 'result', 'expires_at', 'cached_at', 'sql_preview'
        """
        pass  # pragma: no cover
    
    @abstractmethod
    def delete(self, key: str) -> None:
        """
        Elimina una entrada del cache.
        
        Args:
            key: Clave del cache
        """
        pass  # pragma: no cover
    
    @abstractmethod
    def clear(self) -> None:
        """Limpia todo el cache."""
        pass  # pragma: no cover
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del cache.
        
        Returns:
            Dict con estadísticas
        """
        pass  # pragma: no cover


class MemoryCache(CacheBackend):
    """Backend de cache en memoria (no persistente)."""
    
    def __init__(self):
        """Inicializa cache en memoria."""
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Obtiene valor del cache en memoria."""
        return self._cache.get(key)
    
    def set(self, key: str, value: Dict[str, Any]) -> None:
        """Guarda valor en cache en memoria."""
        self._cache[key] = value
    
    def delete(self, key: str) -> None:
        """Elimina entrada del cache."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Limpia todo el cache."""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache."""
        now = datetime.now()
        active = sum(
            1 for entry in self._cache.values()
            if entry['expires_at'] > now
        )
        
        return {
            'backend': 'memory',
            'total_entries': len(self._cache),
            'active_entries': active,
            'expired_entries': len(self._cache) - active,
        }


class FileCache(CacheBackend):
    """Backend de cache persistente en archivos."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Inicializa cache de archivos.
        
        Args:
            cache_dir: Directorio para almacenar cache.
                      Si es None, usa .data/cache/
        """
        if cache_dir is None:
            project_root = Path(__file__).parent.parent.parent
            cache_dir = str(project_root / ".data" / "cache")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Índice en memoria para performance
        self._index_file = self.cache_dir / "index.json"
        self._index: Dict[str, str] = self._load_index()
        
        logger.info(f"FileCache inicializado en {self.cache_dir}")
    
    def _load_index(self) -> Dict[str, str]:
        """Carga el índice de archivos de cache."""
        if not self._index_file.exists():
            return {}
        
        try:
            with open(self._index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error al cargar índice de cache: {e}")
            return {}
    
    def _save_index(self) -> None:
        """Guarda el índice de archivos de cache."""
        try:
            with open(self._index_file, 'w', encoding='utf-8') as f:
                json.dump(self._index, f)
        except Exception as e:
            logger.error(f"Error al guardar índice de cache: {e}")
    
    def _get_cache_file(self, key: str) -> Path:
        """Obtiene la ruta del archivo de cache para una clave."""
        # Usar primeros 2 caracteres para subdirectorio (evitar muchos archivos en un dir)
        subdir = self.cache_dir / key[:2]
        subdir.mkdir(exist_ok=True)
        return subdir / f"{key}.pkl"
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Obtiene valor del cache de archivos."""
        if key not in self._index:
            return None
        
        cache_file = self._get_cache_file(key)
        
        if not cache_file.exists():
            # Archivo eliminado manualmente, limpiar índice
            del self._index[key]
            self._save_index()
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                value = pickle.load(f)
            
            # Verificar expiración
            if datetime.now() > value['expires_at']:
                # Expirado, eliminar
                self.delete(key)
                return None
            
            return value
            
        except Exception as e:
            logger.warning(f"Error al leer cache de archivo {cache_file}: {e}")
            return None
    
    def set(self, key: str, value: Dict[str, Any]) -> None:
        """Guarda valor en cache de archivos."""
        cache_file = self._get_cache_file(key)
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
            
            # Actualizar índice
            self._index[key] = str(cache_file)
            self._save_index()
            
        except Exception as e:
            logger.error(f"Error al guardar cache en archivo {cache_file}: {e}")
    
    def delete(self, key: str) -> None:
        """Elimina entrada del cache."""
        if key not in self._index:
            return
        
        cache_file = self._get_cache_file(key)
        
        try:
            if cache_file.exists():
                cache_file.unlink()
            
            del self._index[key]
            self._save_index()
            
        except Exception as e:
            logger.warning(f"Error al eliminar cache {cache_file}: {e}")
    
    def clear(self) -> None:
        """Limpia todo el cache."""
        try:
            # Eliminar todos los archivos
            for key in list(self._index.keys()):
                self.delete(key)
            
            logger.info("Cache de archivos limpiado")
            
        except Exception as e:
            logger.error(f"Error al limpiar cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache."""
        now = datetime.now()
        active = 0
        expired = 0
        total_size = 0
        
        for key in list(self._index.keys()):
            cache_file = self._get_cache_file(key)
            
            if not cache_file.exists():
                continue
            
            try:
                total_size += cache_file.stat().st_size
                
                with open(cache_file, 'rb') as f:
                    value = pickle.load(f)
                
                if value['expires_at'] > now:
                    active += 1
                else:
                    expired += 1
                    
            except Exception:
                pass
        
        return {
            'backend': 'file',
            'total_entries': len(self._index),
            'active_entries': active,
            'expired_entries': expired,
            'total_size_bytes': total_size,
            'cache_dir': str(self.cache_dir),
        }
    
    def cleanup_expired(self) -> int:
        """
        Elimina entradas expiradas del cache.
        
        Returns:
            Número de entradas eliminadas
        """
        now = datetime.now()
        expired_keys = []
        
        for key in list(self._index.keys()):
            value = self.get(key)  # get() ya elimina expirados
            if value is None:
                expired_keys.append(key)
        
        logger.info(f"Limpiadas {len(expired_keys)} entradas expiradas del cache de archivos")
        return len(expired_keys)


class RedisCache(CacheBackend):
    """Backend de cache persistente con Redis (opcional)."""
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Inicializa cache de Redis.
        
        Args:
            redis_url: URL de conexión a Redis.
                      Si es None, usa REDIS_URL de env o localhost
        """
        try:
            import redis
        except ImportError:
            raise ImportError(
                "Redis no está instalado. "
                "Instalar con: pip install redis"
            )
        
        if redis_url is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        self.redis_url = redis_url
        self.client = redis.from_url(redis_url, decode_responses=False)
        
        # Verificar conexión
        try:
            self.client.ping()
            logger.info(f"RedisCache conectado a {redis_url}")
        except Exception as e:
            raise ConnectionError(f"No se pudo conectar a Redis: {e}")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Obtiene valor del cache de Redis."""
        try:
            data = self.client.get(key)
            if data is None:
                return None
            
            value = pickle.loads(data)
            
            # Verificar expiración (Redis debería manejar esto, pero por seguridad)
            if datetime.now() > value['expires_at']:
                self.delete(key)
                return None
            
            return value
            
        except Exception as e:
            logger.warning(f"Error al leer de Redis: {e}")
            return None
    
    def set(self, key: str, value: Dict[str, Any]) -> None:
        """Guarda valor en cache de Redis."""
        try:
            data = pickle.dumps(value)
            
            # Calcular TTL para Redis
            ttl_seconds = int((value['expires_at'] - datetime.now()).total_seconds())
            
            if ttl_seconds > 0:
                self.client.setex(key, ttl_seconds, data)
            
        except Exception as e:
            logger.error(f"Error al guardar en Redis: {e}")
    
    def delete(self, key: str) -> None:
        """Elimina entrada del cache."""
        try:
            self.client.delete(key)
        except Exception as e:
            logger.warning(f"Error al eliminar de Redis: {e}")
    
    def clear(self) -> None:
        """Limpia todo el cache."""
        try:
            self.client.flushdb()
            logger.info("Cache de Redis limpiado")
        except Exception as e:
            logger.error(f"Error al limpiar Redis: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache."""
        try:
            info = self.client.info('stats')
            dbsize = self.client.dbsize()
            
            return {
                'backend': 'redis',
                'total_entries': dbsize,
                'active_entries': dbsize,  # Redis auto-expira
                'expired_entries': 0,
                'redis_url': self.redis_url,
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
            }
        except Exception as e:
            logger.warning(f"Error al obtener stats de Redis: {e}")
            return {
                'backend': 'redis',
                'error': str(e)
            }


def get_cache_backend() -> CacheBackend:
    """
    Factory para obtener el backend de cache configurado.
    
    Usa variable de entorno CACHE_BACKEND:
    - 'memory': Cache en memoria (default, no persistente)
    - 'file': Cache en archivos (persistente)
    - 'redis': Cache en Redis (persistente, distribuido)
    
    Returns:
        Instancia de CacheBackend
    """
    backend_default = "redis" if os.getenv("REDIS_URL") else "memory"
    backend_type = os.getenv("CACHE_BACKEND", backend_default).lower()
    
    if backend_type == "file":
        cache_dir = os.getenv("CACHE_DIR")
        return FileCache(cache_dir=cache_dir)
    
    elif backend_type == "redis":
        redis_url = os.getenv("REDIS_URL")
        try:
            return RedisCache(redis_url=redis_url)
        except (ImportError, ConnectionError) as e:
            logger.warning(
                f"No se pudo inicializar RedisCache: {e}. "
                "Usando FileCache como fallback."
            )
            return FileCache()
    
    else:  # memory (default)
        if backend_type != "memory":
            logger.warning(
                f"Backend de cache desconocido: '{backend_type}'. "
                "Usando 'memory' por defecto."
            )
        return MemoryCache()
