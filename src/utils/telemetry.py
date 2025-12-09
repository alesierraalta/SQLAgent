"""Sistema de telemetría con OpenTelemetry (Fase F)."""

import os
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from src.utils.logger import logger


class TelemetryManager:
    """Gestor de telemetría con OpenTelemetry."""
    
    def __init__(self):
        """Inicializa el gestor de telemetría."""
        self.tracer = None
        self.meter = None
        self._initialized = False
        self._enabled = os.getenv("ENABLE_TELEMETRY", "false").lower() in ("true", "1", "yes")
        
        # Métricas
        self.query_counter = None
        self.query_duration_histogram = None
        self.cache_hit_counter = None
        self.error_counter = None
        self.token_counter = None
    
    def _lazy_init(self) -> bool:
        """
        Inicializa OpenTelemetry de manera lazy.
        
        Returns:
            True si se inicializó correctamente, False si falló
        """
        if self._initialized:
            return True
        
        if not self._enabled:
            logger.debug("Telemetría deshabilitada (ENABLE_TELEMETRY=false)")
            return False
        
        try:
            from opentelemetry import trace, metrics
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.resources import Resource
            
            # Crear recurso con información del servicio
            resource = Resource.create({
                "service.name": os.getenv("SERVICE_NAME", "llm-data-warehouse"),
                "service.version": os.getenv("SERVICE_VERSION", "1.0.0"),
            })
            
            # Configurar tracer
            tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(tracer_provider)
            self.tracer = trace.get_tracer(__name__)
            
            # Configurar meter
            meter_provider = MeterProvider(resource=resource)
            metrics.set_meter_provider(meter_provider)
            self.meter = metrics.get_meter(__name__)
            
            # Crear métricas
            self._create_metrics()
            
            self._initialized = True
            logger.info("Telemetría OpenTelemetry inicializada correctamente")
            return True
            
        except ImportError:
            logger.warning(
                "OpenTelemetry no está instalado. "
                "Instalar con: pip install opentelemetry-api opentelemetry-sdk"
            )
            return False
        except Exception as e:
            logger.warning(f"Error al inicializar telemetría: {e}")
            return False
    
    def _create_metrics(self):
        """Crea las métricas de OpenTelemetry."""
        if not self.meter:
            return
        
        # Contador de queries
        self.query_counter = self.meter.create_counter(
            name="sql_queries_total",
            description="Total number of SQL queries executed",
            unit="1"
        )
        
        # Histograma de duración de queries
        self.query_duration_histogram = self.meter.create_histogram(
            name="sql_query_duration_seconds",
            description="Duration of SQL query execution",
            unit="s"
        )
        
        # Contador de cache hits
        self.cache_hit_counter = self.meter.create_counter(
            name="cache_hits_total",
            description="Total number of cache hits",
            unit="1"
        )
        
        # Contador de errores
        self.error_counter = self.meter.create_counter(
            name="sql_errors_total",
            description="Total number of SQL errors",
            unit="1"
        )
        
        # Contador de tokens
        self.token_counter = self.meter.create_counter(
            name="llm_tokens_total",
            description="Total number of LLM tokens used",
            unit="1"
        )
    
    def record_query(
        self,
        duration: float,
        success: bool,
        complexity: str = "unknown",
        cache_hit: bool = False,
        error_type: Optional[str] = None
    ):
        """
        Registra una ejecución de query.
        
        Args:
            duration: Duración en segundos
            success: Si la query fue exitosa
            complexity: Complejidad de la query (simple/complex)
            cache_hit: Si fue cache hit
            error_type: Tipo de error si falló
        """
        if not self._lazy_init():
            return
        
        # Atributos comunes
        attributes = {
            "success": str(success),
            "complexity": complexity,
            "cache_hit": str(cache_hit),
        }
        
        if error_type:
            attributes["error_type"] = error_type
        
        # Registrar contador
        if self.query_counter:
            self.query_counter.add(1, attributes)
        
        # Registrar duración
        if self.query_duration_histogram:
            self.query_duration_histogram.record(duration, attributes)
        
        # Registrar cache hit
        if cache_hit and self.cache_hit_counter:
            self.cache_hit_counter.add(1, {"type": "sql"})
        
        # Registrar error
        if not success and self.error_counter:
            error_attrs = {"error_type": error_type or "unknown"}
            self.error_counter.add(1, error_attrs)
    
    def record_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "unknown"
    ):
        """
        Registra uso de tokens del LLM.
        
        Args:
            input_tokens: Tokens de entrada
            output_tokens: Tokens de salida
            model: Modelo usado
        """
        if not self._lazy_init():
            return
        
        if self.token_counter:
            self.token_counter.add(
                input_tokens,
                {"type": "input", "model": model}
            )
            self.token_counter.add(
                output_tokens,
                {"type": "output", "model": model}
            )
    
    def trace_function(self, span_name: Optional[str] = None):
        """
        Decorador para trazar funciones.
        
        Args:
            span_name: Nombre del span (usa nombre de función si es None)
        
        Returns:
            Decorador
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self._lazy_init():
                    return func(*args, **kwargs)
                
                name = span_name or func.__name__
                
                with self.tracer.start_as_current_span(name) as span:
                    try:
                        # Agregar atributos útiles
                        span.set_attribute("function.name", func.__name__)
                        span.set_attribute("function.module", func.__module__)
                        
                        # Ejecutar función
                        start_time = time.time()
                        result = func(*args, **kwargs)
                        duration = time.time() - start_time
                        
                        # Registrar duración
                        span.set_attribute("duration_seconds", duration)
                        span.set_attribute("success", True)
                        
                        return result
                        
                    except Exception as e:
                        # Registrar error
                        span.set_attribute("success", False)
                        span.set_attribute("error.type", type(e).__name__)
                        span.set_attribute("error.message", str(e))
                        span.record_exception(e)
                        raise
            
            return wrapper
        return decorator


# Instancia global del gestor de telemetría (singleton)
_telemetry_manager: Optional[TelemetryManager] = None


def get_telemetry_manager() -> TelemetryManager:
    """
    Obtiene la instancia global del gestor de telemetría.
    
    Returns:
        TelemetryManager singleton
    """
    global _telemetry_manager
    if _telemetry_manager is None:
        _telemetry_manager = TelemetryManager()
    return _telemetry_manager


def record_query_metrics(
    duration: float,
    success: bool,
    complexity: str = "unknown",
    cache_hit: bool = False,
    error_type: Optional[str] = None
):
    """
    Función helper para registrar métricas de query.
    
    Args:
        duration: Duración en segundos
        success: Si la query fue exitosa
        complexity: Complejidad de la query
        cache_hit: Si fue cache hit
        error_type: Tipo de error si falló
    """
    manager = get_telemetry_manager()
    manager.record_query(
        duration=duration,
        success=success,
        complexity=complexity,
        cache_hit=cache_hit,
        error_type=error_type
    )


def record_token_usage(
    input_tokens: int,
    output_tokens: int,
    model: str = "unknown"
):
    """
    Función helper para registrar uso de tokens.
    
    Args:
        input_tokens: Tokens de entrada
        output_tokens: Tokens de salida
        model: Modelo usado
    """
    manager = get_telemetry_manager()
    manager.record_tokens(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model
    )


def trace_query(span_name: Optional[str] = None):
    """
    Decorador para trazar queries.
    
    Args:
        span_name: Nombre del span
    
    Returns:
        Decorador
    """
    manager = get_telemetry_manager()
    return manager.trace_function(span_name)
