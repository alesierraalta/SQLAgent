"""Agente para explicar queries SQL antes de ejecutarlas."""

import os
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from sqlalchemy import Engine, text

from src.utils.logger import logger

# Cargar variables de entorno
load_dotenv()


def explain_query(sql: str, engine: Engine) -> str:
    """
    Explica qué hace una query SQL usando LLM y EXPLAIN plan de PostgreSQL.
    
    Args:
        sql: Query SQL a explicar
        engine: SQLAlchemy Engine para obtener EXPLAIN plan
        
    Returns:
        Explicación en lenguaje natural de la query
    """
    try:
        # Obtener EXPLAIN plan de PostgreSQL
        explain_plan = _get_explain_plan(sql, engine)
        
        # Generar explicación usando LLM
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        llm = ChatOpenAI(model=model_name, temperature=0)
        
        prompt = f"""Eres un experto en SQL y bases de datos. Explica de forma clara y concisa qué hace esta query SQL.

Query SQL:
{sql}

Plan de Ejecución (EXPLAIN):
{explain_plan}

Proporciona una explicación en lenguaje natural que incluya:
1. Qué datos se están consultando
2. Qué operaciones se realizan (JOINs, agregaciones, filtros, etc.)
3. Qué resultado se espera obtener
4. Si hay alguna operación costosa según el plan de ejecución

Explicación:"""
        
        response = llm.invoke(prompt)
        explanation = response.content if hasattr(response, 'content') else str(response)
        
        logger.info("Explicación de query generada exitosamente")
        return explanation
        
    except Exception as e:
        logger.error(f"Error al generar explicación: {e}")
        return f"Error al generar explicación: {str(e)}"


def _get_explain_plan(sql: str, engine: Engine) -> str:
    """
    Obtiene el plan de ejecución (EXPLAIN) de PostgreSQL para una query.
    
    Args:
        sql: Query SQL
        engine: SQLAlchemy Engine
        
    Returns:
        Plan de ejecución como string
    """
    try:
        with engine.connect() as conn:
            # Ejecutar EXPLAIN ANALYZE (si es seguro) o solo EXPLAIN
            # Por seguridad, solo EXPLAIN (no ejecuta la query)
            explain_sql = f"EXPLAIN (FORMAT TEXT) {sql}"
            result = conn.execute(text(explain_sql))
            plan_lines = [row[0] for row in result]
            return "\n".join(plan_lines)
    except Exception as e:
        logger.warning(f"Error al obtener EXPLAIN plan: {e}")
        return f"Error al obtener plan de ejecución: {str(e)}"


def explain_query_simple(sql: str) -> str:
    """
    Explica una query SQL de forma simple sin usar EXPLAIN plan.
    
    Útil cuando no se puede ejecutar EXPLAIN o se quiere una explicación más rápida.
    
    Args:
        sql: Query SQL a explicar
        
    Returns:
        Explicación simple en lenguaje natural
    """
    try:
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        llm = ChatOpenAI(model=model_name, temperature=0)
        
        prompt = f"""Explica de forma clara y concisa qué hace esta query SQL:

{sql}

Explicación breve:"""
        
        response = llm.invoke(prompt)
        explanation = response.content if hasattr(response, 'content') else str(response)
        
        return explanation
        
    except Exception as e:
        logger.error(f"Error al generar explicación simple: {e}")
        return f"Error al generar explicación: {str(e)}"
