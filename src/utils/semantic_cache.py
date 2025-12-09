"""Sistema de cache semántico para queries similares usando embeddings."""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from src.utils.logger import logger

# Cache en memoria para embeddings y resultados
_semantic_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # Default: 1 hora
_similarity_threshold = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.90"))  # Default: 0.90

# Modelo de embeddings (cargado lazy)
_embedding_model = None
_embedding_cache: Dict[str, Any] = {}  # Cache de embeddings calculados


def preload_embedding_model() -> bool:
    """
    Pre-carga el modelo de embeddings para evitar latencia en primera query.
    
    Returns:
        True si el modelo se cargó exitosamente, False en caso contrario
    """
    global _embedding_model
    
    # Verificar si semantic caching está habilitado
    if os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() not in ("true", "1", "yes"):
        return False
    
    # Si ya está cargado, no hacer nada
    if _embedding_model is not None:
        return True
    
    try:
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        logger.info(f"Pre-cargando modelo de embeddings: {model_name}")
        _embedding_model = SentenceTransformer(model_name)
        logger.info("Modelo de embeddings pre-cargado exitosamente")
        return True
    except ImportError:
        logger.warning(
            "sentence-transformers no está instalado. "
            "Semantic caching deshabilitado. "
            "Instala con: pip install sentence-transformers"
        )
        _embedding_model = None
        return False
    except Exception as e:
        logger.error(f"Error al pre-cargar modelo de embeddings: {e}")
        _embedding_model = None
        return False


def initialize_semantic_cache() -> None:
    """
    Inicializa el semantic cache pre-cargando el modelo si está habilitado.
    
    Esta función debe llamarse al inicio de la aplicación para evitar
    latencia en la primera query.
    """
    preload_embedding_model()


def _get_embedding_model():
    """
    Carga el modelo de embeddings (lazy loading).
    
    Returns:
        SentenceTransformer model
    """
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            logger.info(f"Cargando modelo de embeddings: {model_name}")
            _embedding_model = SentenceTransformer(model_name)
            logger.info("Modelo de embeddings cargado exitosamente")
        except ImportError:
            logger.warning(
                "sentence-transformers no está instalado. "
                "Semantic caching deshabilitado. "
                "Instala con: pip install sentence-transformers"
            )
            _embedding_model = None
        except Exception as e:
            logger.error(f"Error al cargar modelo de embeddings: {e}")
            _embedding_model = None
    return _embedding_model


def _compute_embedding(text: str) -> Optional[Any]:
    """
    Calcula embedding para un texto (con cache para evitar recalcular).
    
    Args:
        text: Texto a convertir a embedding
        
    Returns:
        Embedding vector o None si hay error
    """
    # Verificar cache primero
    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
    if text_hash in _embedding_cache:
        return _embedding_cache[text_hash]
    
    model = _get_embedding_model()
    if model is None:
        return None
    
    try:
        embedding = model.encode(text, convert_to_tensor=False, normalize_embeddings=True)
        # Guardar en cache (limitar tamaño para no consumir mucha memoria)
        if len(_embedding_cache) < 1000:  # Máximo 1000 embeddings cacheados
            _embedding_cache[text_hash] = embedding
        return embedding
    except Exception as e:
        logger.warning(f"Error al calcular embedding: {e}")
        return None


def _compute_similarity(embedding1: Any, embedding2: Any) -> float:
    """
    Calcula cosine similarity entre dos embeddings.
    
    Args:
        embedding1: Primer embedding
        embedding2: Segundo embedding
        
    Returns:
        Cosine similarity (0.0 a 1.0)
    """
    try:
        import numpy as np
        
        # Convertir a numpy arrays si es necesario
        if hasattr(embedding1, 'numpy'):
            embedding1 = embedding1.numpy()
        if hasattr(embedding2, 'numpy'):
            embedding2 = embedding2.numpy()
        
        # Calcular cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    except Exception as e:
        logger.warning(f"Error al calcular similitud: {e}")
        return 0.0


def get_semantic_cached_result(question: str) -> Optional[Tuple[str, str]]:
    """
    Busca resultado cacheado por similitud semántica.
    
    Args:
        question: Pregunta del usuario
        
    Returns:
        Tupla (result, sql) si se encuentra cache hit, None en caso contrario
    """
    # Verificar si semantic caching está habilitado
    if os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() not in ("true", "1", "yes"):
        return None
    
    model = _get_embedding_model()
    if model is None:
        return None
    
    # Calcular embedding de la pregunta
    question_embedding = _compute_embedding(question)
    if question_embedding is None:
        return None
    
    # Buscar en cache
    best_match = None
    best_similarity = 0.0
    now = datetime.now()
    
    for cache_key, cache_entry in _semantic_cache.items():
        # Verificar si expiró
        if cache_entry.get('expires_at', now) <= now:
            continue
        
        # Obtener embedding cacheado
        cached_embedding = cache_entry.get('embedding')
        if cached_embedding is None:
            continue
        
        # Calcular similitud
        similarity = _compute_similarity(question_embedding, cached_embedding)
        
        if similarity >= _similarity_threshold and similarity > best_similarity:
            best_similarity = similarity
            best_match = cache_entry
    
    if best_match:
        logger.info(
            f"Semantic cache hit (similarity: {best_similarity:.3f}) para pregunta: {question[:50]}..."
        )
        return (best_match['result'], best_match.get('sql', ''))
    
    return None


def set_semantic_cached_result(
    question: str, 
    result: str, 
    sql: str,
    ttl_seconds: Optional[int] = None
) -> None:
    """
    Guarda resultado en cache semántico.
    
    Args:
        question: Pregunta del usuario
        result: Resultado de la query
        sql: SQL generado
        ttl_seconds: Tiempo de vida en segundos (None = usar default)
    """
    # Verificar si semantic caching está habilitado
    if os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() not in ("true", "1", "yes"):
        return
    
    model = _get_embedding_model()
    if model is None:
        return
    
    # Calcular embedding
    embedding = _compute_embedding(question)
    if embedding is None:
        return
    
    # Generar key único basado en hash del embedding (primeros bytes)
    embedding_hash = hashlib.md5(str(embedding[:10]).encode('utf-8')).hexdigest()
    
    ttl = ttl_seconds or _cache_ttl_seconds
    
    _semantic_cache[embedding_hash] = {
        'question': question,
        'result': result,
        'sql': sql,
        'embedding': embedding,
        'expires_at': datetime.now() + timedelta(seconds=ttl),
        'cached_at': datetime.now(),
        'similarity_threshold': _similarity_threshold,
    }
    
    logger.debug(
        f"Resultado guardado en semantic cache para pregunta: {question[:50]}... (TTL: {ttl}s)"
    )


def clear_semantic_cache() -> None:
    """Limpia todo el cache semántico."""
    global _semantic_cache, _embedding_cache
    _semantic_cache.clear()
    _embedding_cache.clear()
    logger.info("Semantic cache y embedding cache limpiados")


def get_semantic_cache_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas del cache semántico.
    
    Returns:
        Diccionario con estadísticas
    """
    now = datetime.now()
    active_entries = sum(
        1 for entry in _semantic_cache.values() 
        if entry.get('expires_at', now) > now
    )
    expired_entries = len(_semantic_cache) - active_entries
    
    return {
        'total_entries': len(_semantic_cache),
        'active_entries': active_entries,
        'expired_entries': expired_entries,
        'similarity_threshold': _similarity_threshold,
        'ttl_seconds': _cache_ttl_seconds,
    }


def cleanup_expired_semantic_cache() -> None:
    """Elimina entradas expiradas del cache semántico."""
    now = datetime.now()
    expired_keys = [
        key for key, entry in _semantic_cache.items()
        if entry.get('expires_at', now) <= now
    ]
    
    for key in expired_keys:
        del _semantic_cache[key]
    
    if expired_keys:
        logger.debug(f"Limpiadas {len(expired_keys)} entradas expiradas del semantic cache")
