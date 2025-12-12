"""Agente para recuperación automática de errores SQL."""

import re
from typing import Any, Optional

from dotenv import load_dotenv

from src.utils.llm_factory import get_chat_model
from src.utils.logger import logger

# Cargar variables de entorno
load_dotenv()


def recover_from_error(
    original_sql: str,
    error_message: str,
    schema_info: str,
) -> Optional[str]:
    """
    Intenta recuperar una query SQL que falló analizando el error y generando una corrección.
    
    Primero busca en patrones conocidos (aprendizaje previo), luego usa LLM si es necesario.
    
    Args:
        original_sql: SQL original que falló
        error_message: Mensaje de error de PostgreSQL
        schema_info: Información del schema (tablas y columnas disponibles)
        
    Returns:
        SQL corregido o None si no se puede recuperar
    """
    try:
        # Analizar el tipo de error
        error_type = _classify_error(error_message)
        
        # FASE D: Buscar corrección en patrones conocidos primero
        from src.utils.error_patterns import get_error_pattern_store
        
        pattern_store = get_error_pattern_store()
        known_correction = pattern_store.find_correction(
            original_sql=original_sql,
            error_message=error_message,
            error_type=error_type
        )
        
        if known_correction:
            logger.info(
                f"Corrección encontrada en patrones conocidos (tipo: {error_type}). "
                "Evitando llamada a LLM."
            )
            return known_correction
        
        # Si no hay patrón conocido, usar LLM para generar corrección
        logger.info(f"No hay patrón conocido, generando corrección con LLM (tipo: {error_type})")
        
        llm = get_chat_model(temperature=0, require_tools=False)
        
        prompt = f"""Eres un experto en SQL y PostgreSQL. Una query SQL falló y necesitas corregirla.

SQL Original:
{original_sql}

Error de PostgreSQL:
{error_message}

Tipo de Error: {error_type}

Schema Disponible:
{schema_info}

Analiza el error y genera una query SQL corregida que:
1. Solucione el problema específico del error
2. Mantenga la intención original de la query
3. Use solo tablas y columnas del schema disponible
4. Sea válida sintácticamente

Responde SOLO con el SQL corregido, sin explicaciones adicionales."""
        
        response = llm.invoke(prompt)
        corrected_sql = response.content.strip() if hasattr(response, 'content') else str(response).strip()
        
        # Limpiar la respuesta (puede contener markdown code blocks)
        corrected_sql = _clean_sql_response(corrected_sql)
        
        logger.info(f"Query corregida generada: {corrected_sql[:100]}...")
        return corrected_sql
        
    except Exception as e:
        logger.error(f"Error al generar query corregida: {e}")
        return None


def _classify_error(error_message: str) -> str:
    """
    Clasifica el tipo de error SQL basado en el mensaje.
    
    Args:
        error_message: Mensaje de error de PostgreSQL
        
    Returns:
        Tipo de error clasificado
    """
    error_lower = error_message.lower()
    
    if "column" in error_lower and ("does not exist" in error_lower or "no existe" in error_lower):
        return "COLUMN_NOT_FOUND"
    elif "table" in error_lower and ("does not exist" in error_lower or "no existe" in error_lower):
        return "TABLE_NOT_FOUND"
    elif "syntax error" in error_lower or "error de sintaxis" in error_lower:
        return "SYNTAX_ERROR"
    elif "type" in error_lower and "mismatch" in error_lower:
        return "TYPE_MISMATCH"
    elif "group by" in error_lower or "aggregate" in error_lower:
        return "AGGREGATE_ERROR"
    elif "join" in error_lower or "relation" in error_lower:
        return "JOIN_ERROR"
    else:
        return "UNKNOWN_ERROR"


def _clean_sql_response(response: str) -> str:
    """
    Limpia la respuesta del LLM para extraer solo el SQL.
    
    Args:
        response: Respuesta del LLM que puede contener markdown o explicaciones
        
    Returns:
        SQL limpio
    """
    # Remover markdown code blocks
    sql = response
    
    # Buscar SQL dentro de ```sql ... ```
    sql_block_match = re.search(r'```(?:sql)?\s*(.*?)\s*```', sql, re.DOTALL | re.IGNORECASE)
    if sql_block_match:
        sql = sql_block_match.group(1).strip()
    
    # Remover líneas que parecen explicaciones (no empiezan con SELECT, WITH, etc.)
    lines = sql.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Si la línea está vacía o es un comentario, mantenerla
        if not stripped or stripped.startswith('--'):
            cleaned_lines.append(line)
        # Si parece SQL (empieza con palabra clave SQL), mantenerla
        elif re.match(r'^\s*(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|EXPLAIN)', stripped, re.IGNORECASE):
            cleaned_lines.append(line)
        # Si contiene operadores SQL comunes, mantenerla
        elif any(op in stripped.upper() for op in ['FROM', 'WHERE', 'JOIN', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'UNION']):
            cleaned_lines.append(line)
        # Si es parte de una expresión SQL (contiene paréntesis, comas, etc.), mantenerla
        elif any(char in stripped for char in ['(', ')', ',', '=', '<', '>', "'", '"']):
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()


def should_attempt_recovery(error_message: str) -> bool:
    """
    Determina si se debe intentar recuperación automática basado en el tipo de error.
    
    Algunos errores no son recuperables automáticamente (ej: permisos, conexión).
    
    Args:
        error_message: Mensaje de error
        
    Returns:
        True si se debe intentar recuperación, False en caso contrario
    """
    error_lower = error_message.lower()
    
    # Errores que NO son recuperables automáticamente
    non_recoverable_patterns = [
        'permission denied',
        'connection',
        'timeout',
        'authentication',
        'authorization',
        'access denied',
        'permiso denegado',
        'conexión',
        'autenticación',
    ]
    
    for pattern in non_recoverable_patterns:
        if pattern in error_lower:
            return False
    
    # Errores que SÍ son recuperables
    recoverable_patterns = [
        'column',
        'table',
        'syntax',
        'type',
        'group by',
        'aggregate',
        'join',
        'does not exist',
        'no existe',
    ]
    
    for pattern in recoverable_patterns:
        if pattern in error_lower:
            return True
    
    # Por defecto, intentar recuperación para errores desconocidos
    return True


def report_successful_correction(
    original_sql: str,
    error_message: str,
    corrected_sql: str
) -> None:
    """
    Reporta una corrección exitosa para aprendizaje futuro (Fase D).
    
    Args:
        original_sql: SQL original que falló
        error_message: Mensaje de error
        corrected_sql: SQL corregido que funcionó
    """
    from src.utils.error_patterns import get_error_pattern_store
    
    error_type = _classify_error(error_message)
    pattern_store = get_error_pattern_store()
    
    pattern_store.store_successful_correction(
        original_sql=original_sql,
        error_message=error_message,
        error_type=error_type,
        corrected_sql=corrected_sql
    )
    
    logger.info(f"Corrección exitosa reportada para aprendizaje (tipo: {error_type})")
