"""Monitoreo de performance de queries SQL."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import logger

# Ruta del archivo de métricas
PERFORMANCE_FILE = Path.home() / ".llm_dw_performance.json"
MAX_ENTRIES = 1000  # Máximo de entradas en el archivo


class QueryPerformanceMetrics:
    """Métricas de performance para una query individual."""
    
    def __init__(
        self,
        sql: str,
        execution_time: float,
        success: bool,
        error_message: Optional[str] = None,
        rows_returned: Optional[int] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        tokens_total: Optional[int] = None,
        cache_hit_type: Optional[str] = None,
        model_used: Optional[str] = None,
    ):
        """
        Inicializa métricas de performance.
        
        Args:
            sql: Query SQL ejecutada
            execution_time: Tiempo de ejecución en segundos
            success: Si la query fue exitosa
            error_message: Mensaje de error si falló
            rows_returned: Número de filas retornadas (si exitosa)
            tokens_input: Tokens de input usados (opcional)
            tokens_output: Tokens de output generados (opcional)
            tokens_total: Total de tokens (opcional)
            cache_hit_type: Tipo de cache hit ("semantic", "sql", "none") (opcional)
            model_used: Modelo LLM usado ("gpt-4o", "gpt-4o-mini", etc.) (opcional)
        """
        self.timestamp = datetime.now().isoformat()
        self.sql = sql
        self.execution_time = execution_time
        self.success = success
        self.error_message = error_message
        self.rows_returned = rows_returned
        self.tokens_input = tokens_input
        self.tokens_output = tokens_output
        self.tokens_total = tokens_total
        self.cache_hit_type = cache_hit_type
        self.model_used = model_used
        self.sql_hash = self._hash_sql(sql)
    
    def _hash_sql(self, sql: str) -> str:
        """Genera hash simple del SQL para agrupar queries similares."""
        import hashlib
        # Normalizar SQL básico (eliminar espacios extras)
        normalized = " ".join(sql.split())
        return hashlib.md5(normalized.encode()).hexdigest()[:8]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte métricas a diccionario para serialización."""
        return {
            "timestamp": self.timestamp,
            "sql": self.sql,
            "sql_hash": self.sql_hash,
            "execution_time": self.execution_time,
            "success": self.success,
            "error_message": self.error_message,
            "rows_returned": self.rows_returned,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "tokens_total": self.tokens_total,
            "cache_hit_type": self.cache_hit_type,
            "model_used": self.model_used,
        }


def record_query_performance(
    sql: str,
    execution_time: float,
    success: bool = True,
    error_message: Optional[str] = None,
    rows_returned: Optional[int] = None,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None,
    tokens_total: Optional[int] = None,
    cache_hit_type: Optional[str] = None,
    model_used: Optional[str] = None,
) -> None:
    """
    Registra métricas de performance de una query.
    
    Args:
        sql: Query SQL ejecutada
        execution_time: Tiempo de ejecución en segundos
        success: Si la query fue exitosa
        error_message: Mensaje de error si falló
        rows_returned: Número de filas retornadas
        tokens_input: Tokens de input usados (opcional)
        tokens_output: Tokens de output generados (opcional)
        tokens_total: Total de tokens (opcional)
        cache_hit_type: Tipo de cache hit ("semantic", "sql", "none") (opcional)
        model_used: Modelo LLM usado (opcional)
    """
    try:
        metrics = QueryPerformanceMetrics(
            sql=sql,
            execution_time=execution_time,
            success=success,
            error_message=error_message,
            rows_returned=rows_returned,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_total=tokens_total,
            cache_hit_type=cache_hit_type,
            model_used=model_used,
        )
        
        # Cargar métricas existentes
        all_metrics = load_performance_metrics()
        
        # Agregar nueva métrica
        all_metrics.append(metrics.to_dict())
        
        # Limitar tamaño (mantener solo las más recientes)
        if len(all_metrics) > MAX_ENTRIES:
            all_metrics = all_metrics[-MAX_ENTRIES:]
        
        # Guardar
        with open(PERFORMANCE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_metrics, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Métricas de performance guardadas: {execution_time:.2f}s")
        
    except Exception as e:
        logger.warning(f"Error al guardar métricas de performance: {e}")


def load_performance_metrics(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Carga métricas de performance.
    
    Args:
        limit: Número máximo de entradas a retornar (None = todas)
        
    Returns:
        Lista de métricas de performance
    """
    try:
        if not PERFORMANCE_FILE.exists():
            return []
        
        with open(PERFORMANCE_FILE, "r", encoding="utf-8") as f:
            metrics = json.load(f)
        
        if limit:
            return metrics[-limit:]
        
        return metrics
        
    except Exception as e:
        logger.warning(f"Error al cargar métricas de performance: {e}")
        return []


def get_slow_queries(threshold_seconds: float = 5.0, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Obtiene queries lentas (por encima del threshold).
    
    Args:
        threshold_seconds: Tiempo mínimo en segundos para considerar una query lenta
        limit: Número máximo de queries a retornar
        
    Returns:
        Lista de queries lentas ordenadas por tiempo de ejecución (descendente)
    """
    all_metrics = load_performance_metrics()
    
    slow_queries = [
        m for m in all_metrics
        if m.get("execution_time", 0) >= threshold_seconds 
        and m.get("success", False)
        and m.get("sql", "").strip()  # Solo queries con SQL válido
    ]
    
    # Eliminar duplicados basados en SQL hash y timestamp
    seen = set()
    unique_queries = []
    for query in slow_queries:
        # Usar hash SQL + timestamp como key único
        key = (query.get("sql_hash", ""), query.get("timestamp", ""))
        if key not in seen and key[0]:  # Solo si tiene hash válido
            seen.add(key)
            unique_queries.append(query)
    
    # Ordenar por tiempo de ejecución (descendente)
    unique_queries.sort(key=lambda x: x.get("execution_time", 0), reverse=True)
    
    return unique_queries[:limit]


def get_failed_queries(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Obtiene queries que fallaron.
    
    Args:
        limit: Número máximo de queries a retornar
        
    Returns:
        Lista de queries fallidas ordenadas por timestamp (más recientes primero)
    """
    all_metrics = load_performance_metrics()
    
    failed_queries = [
        m for m in all_metrics
        if not m.get("success", True)
    ]
    
    # Ordenar por timestamp (descendente = más recientes primero)
    failed_queries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return failed_queries[:limit]


def get_performance_stats(days: int = 7) -> Dict[str, Any]:
    """
    Obtiene estadísticas agregadas de performance.
    
    Args:
        days: Número de días hacia atrás para analizar
        
    Returns:
        Diccionario con estadísticas agregadas
    """
    all_metrics = load_performance_metrics()
    
    # Filtrar por fecha
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_metrics = [
        m for m in all_metrics
        if datetime.fromisoformat(m.get("timestamp", "2000-01-01")) >= cutoff_date
    ]
    
    if not recent_metrics:
        return {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_execution_time": 0.0,
            "min_execution_time": 0.0,
            "max_execution_time": 0.0,
            "slow_queries_count": 0,
        }
    
    successful = [m for m in recent_metrics if m.get("success", False)]
    failed = [m for m in recent_metrics if not m.get("success", True)]
    
    # Filtrar execution times válidos (> 0) para cálculos más precisos
    execution_times = [
        m.get("execution_time", 0) for m in successful 
        if m.get("execution_time", 0) > 0
    ]
    
    slow_threshold = 5.0  # 5 segundos
    slow_count = sum(1 for t in execution_times if t >= slow_threshold)
    
    # Si no hay execution times válidos, usar todos (incluyendo 0)
    if not execution_times:
        execution_times = [m.get("execution_time", 0) for m in successful]
    
    # Calcular métricas de tokens
    tokens_total_list = [m.get("tokens_total", 0) for m in recent_metrics if m.get("tokens_total")]
    avg_tokens_total = sum(tokens_total_list) / len(tokens_total_list) if tokens_total_list else None
    
    # Calcular cache hit rate
    cache_hits = {
        "semantic": sum(1 for m in recent_metrics if m.get("cache_hit_type") == "semantic"),
        "sql": sum(1 for m in recent_metrics if m.get("cache_hit_type") == "sql"),
        "none": sum(1 for m in recent_metrics if m.get("cache_hit_type") in (None, "none")),
    }
    total_cache_hits = cache_hits["semantic"] + cache_hits["sql"]
    cache_hit_rate = (total_cache_hits / len(recent_metrics) * 100) if recent_metrics else 0.0
    
    # Distribución de modelos
    model_distribution = {}
    for m in recent_metrics:
        model = m.get("model_used") or "N/A"
        model_distribution[model] = model_distribution.get(model, 0) + 1
    
    return {
        "total_queries": len(recent_metrics),
        "successful_queries": len(successful),
        "failed_queries": len(failed),
        "success_rate": len(successful) / len(recent_metrics) * 100 if recent_metrics else 0,
        "avg_execution_time": sum(execution_times) / len(execution_times) if execution_times else 0.0,
        "min_execution_time": min(execution_times) if execution_times else 0.0,
        "max_execution_time": max(execution_times) if execution_times else 0.0,
        "slow_queries_count": slow_count,
        "period_days": days,
        "avg_tokens_total": avg_tokens_total,
        "cache_hit_rate": cache_hit_rate,
        "semantic_cache_hits": cache_hits["semantic"],
        "sql_cache_hits": cache_hits["sql"],
        "model_distribution": model_distribution,
    }


def get_query_patterns(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Identifica patrones de queries (queries similares agrupadas por hash).
    
    Args:
        limit: Número máximo de patrones a retornar
        
    Returns:
        Lista de patrones con estadísticas agregadas
    """
    all_metrics = load_performance_metrics()
    
    # Agrupar por hash SQL
    patterns: Dict[str, Dict[str, Any]] = {}
    
    for metric in all_metrics:
        sql_hash = metric.get("sql_hash", "unknown")
        
        if sql_hash not in patterns:
            patterns[sql_hash] = {
                "sql_hash": sql_hash,
                "sql_preview": metric.get("sql", "")[:100],
                "count": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "success_count": 0,
                "fail_count": 0,
            }
        
        pattern = patterns[sql_hash]
        pattern["count"] += 1
        pattern["total_time"] += metric.get("execution_time", 0)
        
        if metric.get("success", False):
            pattern["success_count"] += 1
        else:
            pattern["fail_count"] += 1
    
    # Calcular promedios y filtrar patrones sin SQL válido
    valid_patterns = []
    for pattern in patterns.values():
        if pattern["count"] > 0:
            pattern["avg_time"] = pattern["total_time"] / pattern["count"]
            # Solo incluir patrones con SQL preview válido
            if pattern.get("sql_preview", "").strip():
                valid_patterns.append(pattern)
    
    # Ordenar por frecuencia (descendente)
    sorted_patterns = sorted(valid_patterns, key=lambda x: x["count"], reverse=True)
    
    return sorted_patterns[:limit]


def clear_performance_metrics() -> None:
    """Limpia todas las métricas de performance."""
    try:
        if PERFORMANCE_FILE.exists():
            PERFORMANCE_FILE.unlink()
        logger.info("Métricas de performance limpiadas")
    except Exception as e:
        logger.warning(f"Error al limpiar métricas: {e}")
