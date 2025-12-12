"""Gestión de historial de queries para el sistema LLM-DW."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from src.utils.logger import logger

# Ruta del archivo de historial
HISTORY_FILE = Path.home() / ".llm_dw_history.json"
MAX_HISTORY_ENTRIES = 100
DISABLE_HISTORY = os.getenv("DISABLE_HISTORY", "false").lower() in ("true", "1", "yes")


def save_query(
    question: str,
    sql: str | None = None,
    response: str | None = None,
    success: bool = True,
    cache_hit_type: str | None = None,
    model_used: str | None = None,
) -> None:
    """
    Guarda una query en el historial.

    Args:
        question: Pregunta en lenguaje natural
        sql: SQL generado (opcional)
        response: Respuesta del agente (opcional)
        success: Si la query fue exitosa
        cache_hit_type: Tipo de cache hit (opcional)
        model_used: Modelo usado (opcional)
    """
    if DISABLE_HISTORY:
        logger.debug("Historial deshabilitado por DISABLE_HISTORY=true")
        return
    try:
        # Cargar historial existente
        history = load_history()
        
        # Crear nueva entrada
        entry = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "sql": sql,
            "success": success,
            "response_preview": response[:200] + "..." if response and len(response) > 200 else response,
        }

        if cache_hit_type is not None:
            entry["cache_hit_type"] = cache_hit_type
        if model_used is not None:
            entry["model_used"] = model_used
        
        # Agregar al inicio
        history.insert(0, entry)
        
        # Limitar tamaño
        if len(history) > MAX_HISTORY_ENTRIES:
            history = history[:MAX_HISTORY_ENTRIES]
        
        # Guardar
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Query guardada en historial: {question[:50]}...")
    
    except Exception as e:
        logger.warning(f"Error al guardar en historial: {e}")


def load_history(limit: int | None = None) -> List[Dict[str, Any]]:
    """
    Carga el historial de queries.

    Args:
        limit: Número máximo de entradas a retornar (None = todas)

    Returns:
        Lista de entradas del historial
    """
    try:
        if DISABLE_HISTORY:
            return []
        if not HISTORY_FILE.exists():
            return []
        
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
        
        if limit:
            return history[:limit]
        
        return history
    
    except Exception as e:
        logger.warning(f"Error al cargar historial: {e}")
        return []


def clear_history() -> None:
    """Limpia el historial completo."""
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        logger.info("Historial limpiado")
    except Exception as e:
        logger.warning(f"Error al limpiar historial: {e}")


def get_history_entry(index: int) -> Dict[str, Any] | None:
    """
    Obtiene una entrada específica del historial por índice.

    Args:
        index: Índice de la entrada (0 = más reciente)

    Returns:
        Entrada del historial o None si no existe
    """
    history = load_history()
    if 0 <= index < len(history):
        return history[index]
    return None
