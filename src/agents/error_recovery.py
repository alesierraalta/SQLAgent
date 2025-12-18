"""Agent for automatic SQL error recovery."""

import re
from typing import Any, Optional

from dotenv import load_dotenv

from src.utils.llm_factory import get_chat_model
from src.utils.logger import logger

# Load environment variables
load_dotenv()


def recover_from_error(
    original_sql: str,
    error_message: str,
    schema_info: str,
) -> Optional[str]:
    """
    Attempts to recover a failed SQL query by analyzing the error and generating a correction.
    
    First checks known patterns (prior learning), then uses LLM if necessary.
    
    Args:
        original_sql: Original SQL that failed
        error_message: PostgreSQL error message
        schema_info: Available schema information
        
    Returns:
        Corrected SQL or None if recovery fails
    """
    try:
        # Analyze the error type
        error_type = _classify_error(error_message)
        
        # PHASE D: Search for correction in known patterns first
        from src.utils.error_patterns import get_error_pattern_store
        
        pattern_store = get_error_pattern_store()
        known_correction = pattern_store.find_correction(
            original_sql=original_sql,
            error_message=error_message,
            error_type=error_type
        )
        
        if known_correction:
            logger.info(
                f"Correction found in known patterns (type: {error_type}). "
                "Avoiding LLM call."
            )
            return known_correction
        
        # If no known pattern, use LLM to generate correction
        logger.info(f"No known pattern, generating correction with LLM (type: {error_type})")
        
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
        
        # Clean the response (may contain markdown code blocks)
        corrected_sql = _clean_sql_response(corrected_sql)
        
        logger.info(f"Corrected query generated: {corrected_sql[:100]}...")
        return corrected_sql
        
    except Exception as e:
        logger.error(f"Error generating corrected query: {e}")
        return None


def _classify_error(error_message: str) -> str:
    """
    Classifies the SQL error type based on the message.
    
    Args:
        error_message: PostgreSQL error message
        
    Returns:
        Classified error type
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
    Cleans the LLM response to extract only the SQL.
    
    Args:
        response: LLM response that may contain markdown or explanations
        
    Returns:
        Clean SQL
    """
    # Remove markdown code blocks
    sql = response
    
    # Search for SQL inside ```sql ... ```
    sql_block_match = re.search(r'```(?:sql)?\s*(.*?)\s*```', sql, re.DOTALL | re.IGNORECASE)
    if sql_block_match:
        sql = sql_block_match.group(1).strip()
    
    # Remove lines that look like explanations (don't start with SELECT, WITH, etc.)
    lines = sql.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # If line is empty or a comment, keep it
        if not stripped or stripped.startswith('--'):
            cleaned_lines.append(line)
        # If it looks like SQL (starts with SQL keyword), keep it
        elif re.match(r'^\s*(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|EXPLAIN)', stripped, re.IGNORECASE):
            cleaned_lines.append(line)
        # If it contains common SQL operators, keep it
        elif any(op in stripped.upper() for op in ['FROM', 'WHERE', 'JOIN', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'UNION']):
            cleaned_lines.append(line)
        # If it is part of a SQL expression (contains parens, commas, etc.), keep it
        elif any(char in stripped for char in ['(', ')', ',', '=', '<', '>', "'", '"']):
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines).strip()


def should_attempt_recovery(error_message: str) -> bool:
    """
    Determines if automatic recovery should be attempted based on the error type.
    
    Some errors are not automatically recoverable (e.g., permissions, connection).
    
    Args:
        error_message: Error message
        
    Returns:
        True if recovery should be attempted, False otherwise
    """
    error_lower = error_message.lower()
    
    # Errors that are NOT automatically recoverable
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
    
    # Errors that ARE recoverable
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
    
    # Default to attempting recovery for unknown errors
    return True


def report_successful_correction(
    original_sql: str,
    error_message: str,
    corrected_sql: str
) -> None:
    """
    Reports a successful correction for future learning (Phase D).
    
    Args:
        original_sql: Original SQL that failed
        error_message: Error message
        corrected_sql: Corrected SQL that worked
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
    
    logger.info(f"Successful correction reported for learning (type: {error_type})")
