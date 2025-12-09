"""Banco de ejemplos few-shot para mejorar precisión y reducir tokens."""

import os
from typing import Dict, List, Optional

from src.utils.logger import logger

# Banco de ejemplos categorizados
_EXAMPLES_BANK: Dict[str, List[Dict[str, str]]] = {
    "aggregation": [
        {
            "input": "¿Cuál es el total de revenue?",
            "query": "SELECT SUM(revenue) AS total_revenue FROM sales;"
        },
        {
            "input": "Cuenta cuántas ventas hay",
            "query": "SELECT COUNT(*) AS total_ventas FROM sales;"
        },
        {
            "input": "Promedio de revenue por transacción",
            "query": "SELECT AVG(revenue) AS promedio_revenue FROM sales;"
        },
    ],
    "group_by": [
        {
            "input": "Total de revenue por país",
            "query": "SELECT country, SUM(revenue) AS total_revenue FROM sales GROUP BY country ORDER BY total_revenue DESC;"
        },
        {
            "input": "Ventas por mes",
            "query": "SELECT DATE_TRUNC('month', date) AS mes, SUM(revenue) AS total FROM sales GROUP BY mes ORDER BY mes;"
        },
        {
            "input": "Cantidad de productos por categoría",
            "query": "SELECT category, COUNT(*) AS cantidad FROM products GROUP BY category;"
        },
    ],
    "join": [
        {
            "input": "Productos con sus ventas totales",
            "query": "SELECT p.name, p.category, COALESCE(SUM(s.revenue), 0) AS total_ventas FROM products p LEFT JOIN sales s ON p.id = s.product_id GROUP BY p.id, p.name, p.category ORDER BY total_ventas DESC;"
        },
        {
            "input": "Ventas con información del producto",
            "query": "SELECT s.date, s.country, p.name AS producto, s.revenue FROM sales s JOIN products p ON s.product_id = p.id ORDER BY s.date DESC;"
        },
    ],
    "filter": [
        {
            "input": "Ventas de enero de 2024",
            "query": "SELECT * FROM sales WHERE date >= '2024-01-01' AND date < '2024-02-01' ORDER BY date;"
        },
        {
            "input": "Productos con precio mayor a 100",
            "query": "SELECT * FROM products WHERE price > 100 ORDER BY price DESC;"
        },
        {
            "input": "Ventas de España",
            "query": "SELECT * FROM sales WHERE country = 'España' ORDER BY date DESC;"
        },
    ],
    "top_n": [
        {
            "input": "Top 10 productos por ventas",
            "query": "SELECT p.name, SUM(s.revenue) AS total_ventas FROM products p JOIN sales s ON p.id = s.product_id GROUP BY p.id, p.name ORDER BY total_ventas DESC LIMIT 10;"
        },
        {
            "input": "Países con más revenue",
            "query": "SELECT country, SUM(revenue) AS total_revenue FROM sales GROUP BY country ORDER BY total_revenue DESC LIMIT 5;"
        },
    ],
}


def _detect_query_type(question: str) -> str:
    """
    Detecta el tipo de query basado en keywords.
    
    Args:
        question: Pregunta del usuario
        
    Returns:
        Tipo de query detectado
    """
    question_lower = question.lower()
    
    # Detectar tipo por keywords
    if any(kw in question_lower for kw in ["top", "mejor", "peor", "más", "menos", "ranking"]):
        return "top_n"
    elif any(kw in question_lower for kw in ["join", "con", "relacion", "producto", "venta"]):
        return "join"
    elif any(kw in question_lower for kw in ["por", "agrupar", "group"]):
        return "group_by"
    elif any(kw in question_lower for kw in ["filtro", "donde", "where", "de", "en", "desde", "hasta"]):
        return "filter"
    elif any(kw in question_lower for kw in ["total", "suma", "sum", "count", "cuenta", "promedio", "avg"]):
        return "aggregation"
    
    # Por defecto, usar aggregation
    return "aggregation"


def get_relevant_examples(question: str, max_examples: int = 2) -> List[Dict[str, str]]:
    """
    Obtiene ejemplos relevantes para una pregunta.
    
    Args:
        question: Pregunta del usuario
        max_examples: Número máximo de ejemplos a retornar
        
    Returns:
        Lista de ejemplos relevantes
    """
    # Verificar si few-shot está habilitado
    if os.getenv("ENABLE_FEW_SHOT", "true").lower() not in ("true", "1", "yes"):
        return []
    
    # Detectar tipo de query
    query_type = _detect_query_type(question)
    
    # Obtener ejemplos del tipo detectado
    examples = _EXAMPLES_BANK.get(query_type, [])
    
    # Limitar número de ejemplos
    selected_examples = examples[:max_examples]
    
    if selected_examples:
        logger.debug(f"Seleccionados {len(selected_examples)} ejemplos few-shot de tipo '{query_type}'")
    
    return selected_examples


def format_examples_for_prompt(examples: List[Dict[str, str]]) -> str:
    """
    Formatea ejemplos para incluir en el prompt.
    
    Args:
        examples: Lista de ejemplos
        
    Returns:
        String formateado con ejemplos
    """
    if not examples:
        return ""
    
    lines = ["\nEJEMPLOS:"]
    for i, example in enumerate(examples, 1):
        lines.append(f"{i}. Pregunta: {example['input']}")
        lines.append(f"   SQL: {example['query']}")
    
    return "\n".join(lines)
