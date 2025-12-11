"""Banco de ejemplos few-shot para mejorar precisión y reducir tokens."""

import os
from typing import Dict, List, Optional

from src.utils.logger import logger

# Banco de ejemplos categorizados
_EXAMPLES_BANK: Dict[str, List[Dict[str, str]]] = {
    "aggregation": [
        {
            "input": "¿Cuál es el revenue total y el promedio por país excluyendo países con menos de 50 ventas?",
            "query": """
                WITH ventas_por_pais AS (
                    SELECT country, COUNT(*) AS n_ventas, SUM(revenue) AS total_revenue
                    FROM sales
                    GROUP BY country
                )
                SELECT country, total_revenue, total_revenue / NULLIF(n_ventas, 0) AS avg_revenue
                FROM ventas_por_pais
                WHERE n_ventas >= 50
                ORDER BY total_revenue DESC;
            """
        },
        {
            "input": "Calcula el revenue total de los últimos 90 días y compáralo vs los 90 días anteriores",
            "query": """
                WITH ultimos_90 AS (
                    SELECT SUM(revenue) AS total FROM sales WHERE date >= CURRENT_DATE - INTERVAL '90 days'
                ),
                prev_90 AS (
                    SELECT SUM(revenue) AS total FROM sales WHERE date < CURRENT_DATE - INTERVAL '90 days' AND date >= CURRENT_DATE - INTERVAL '180 days'
                )
                SELECT ultimos_90.total AS revenue_actual,
                       prev_90.total AS revenue_prev,
                       (ultimos_90.total - prev_90.total) AS delta,
                       CASE WHEN prev_90.total = 0 THEN NULL ELSE (ultimos_90.total - prev_90.total) / prev_90.total END AS delta_pct
                FROM ultimos_90, prev_90;
            """
        },
        {
            "input": "Promedio móvil de revenue 7 días para los últimos 30",
            "query": """
                SELECT date::date AS dia,
                       SUM(revenue) AS revenue_dia,
                       AVG(SUM(revenue)) OVER (ORDER BY date::date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS avg_7d
                FROM sales
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY date::date
                ORDER BY dia;
            """
        },
    ],
    "group_by": [
        {
            "input": "Revenue mensual y crecimiento vs mes anterior por categoría",
            "query": """
                WITH mensuales AS (
                    SELECT DATE_TRUNC('month', s.date) AS mes,
                           p.category,
                           SUM(s.revenue) AS revenue_mes
                    FROM sales s
                    JOIN products p ON p.id = s.product_id
                    GROUP BY mes, p.category
                )
                SELECT mes,
                       category,
                       revenue_mes,
                       LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes) AS revenue_prev,
                       CASE WHEN LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes) = 0 THEN NULL
                            ELSE (revenue_mes - LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes))
                        END AS delta,
                       CASE WHEN LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes) = 0 THEN NULL
                            ELSE (revenue_mes - LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes)) / NULLIF(LAG(revenue_mes) OVER (PARTITION BY category ORDER BY mes),0)
                        END AS delta_pct
                FROM mensuales
                ORDER BY mes, category;
            """
        },
        {
            "input": "Distribución de revenue por país y cuartiles",
            "query": """
                SELECT country,
                       SUM(revenue) AS total_revenue,
                       PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY revenue) AS p25,
                       PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY revenue) AS p50,
                       PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY revenue) AS p75
                FROM sales
                GROUP BY country
                ORDER BY total_revenue DESC;
            """
        },
    ],
    "join": [
        {
            "input": "Top 5 productos por revenue en los últimos 60 días y su participación % por categoría",
            "query": """
                WITH recientes AS (
                    SELECT s.product_id,
                           SUM(s.revenue) AS revenue_total
                    FROM sales s
                    WHERE s.date >= CURRENT_DATE - INTERVAL '60 days'
                    GROUP BY s.product_id
                ),
                por_categoria AS (
                    SELECT p.category, SUM(s.revenue) AS revenue_categoria
                    FROM sales s
                    JOIN products p ON p.id = s.product_id
                    WHERE s.date >= CURRENT_DATE - INTERVAL '60 days'
                    GROUP BY p.category
                )
                SELECT p.name,
                       p.category,
                       r.revenue_total,
                       r.revenue_total / NULLIF(pc.revenue_categoria, 0) AS participation_pct
                FROM recientes r
                JOIN products p ON p.id = r.product_id
                JOIN por_categoria pc ON pc.category = p.category
                ORDER BY r.revenue_total DESC
                LIMIT 5;
            """
        },
        {
            "input": "Ventas detalladas con densidad y ranking por país y fecha",
            "query": """
                SELECT s.date::date AS fecha,
                       s.country,
                       p.name AS producto,
                       s.revenue,
                       DENSE_RANK() OVER (PARTITION BY s.country ORDER BY s.revenue DESC) AS rank_country
                FROM sales s
                JOIN products p ON p.id = s.product_id
                WHERE s.date >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY s.country, s.date DESC;
            """
        },
    ],
    "filter": [
        {
            "input": "Ventas filtradas por rango de fechas dinámico y países específicos",
            "query": """
                SELECT *
                FROM sales
                WHERE date >= CURRENT_DATE - INTERVAL '45 days'
                  AND country IN ('España', 'México', 'Argentina')
                ORDER BY date DESC;
            """
        },
        {
            "input": "Productos sin ventas en los últimos 90 días",
            "query": """
                SELECT p.id, p.name, p.category
                FROM products p
                LEFT JOIN (
                    SELECT DISTINCT product_id
                    FROM sales
                    WHERE date >= CURRENT_DATE - INTERVAL '90 days'
                ) s ON s.product_id = p.id
                WHERE s.product_id IS NULL
                ORDER BY p.name;
            """
        },
    ],
    "top_n": [
        {
            "input": "Top 10 productos por crecimiento de revenue vs mes anterior",
            "query": """
                WITH mensuales AS (
                    SELECT DATE_TRUNC('month', s.date) AS mes,
                           s.product_id,
                           SUM(s.revenue) AS revenue_mes
                    FROM sales s
                    GROUP BY mes, s.product_id
                ),
                con_prev AS (
                    SELECT m.*,
                           LAG(revenue_mes) OVER (PARTITION BY product_id ORDER BY mes) AS revenue_prev
                    FROM mensuales m
                )
                SELECT p.name,
                       p.category,
                       con_prev.mes,
                       con_prev.revenue_mes,
                       con_prev.revenue_prev,
                       (con_prev.revenue_mes - con_prev.revenue_prev) AS delta,
                       CASE WHEN con_prev.revenue_prev = 0 THEN NULL ELSE (con_prev.revenue_mes - con_prev.revenue_prev) / con_prev.revenue_prev END AS delta_pct
                FROM con_prev
                JOIN products p ON p.id = con_prev.product_id
                WHERE con_prev.revenue_prev IS NOT NULL
                ORDER BY delta_pct DESC NULLS LAST
                LIMIT 10;
            """
        },
        {
            "input": "Top 5 países por revenue en el último trimestre y su share del total",
            "query": """
                WITH trimestre AS (
                    SELECT country, SUM(revenue) AS total_revenue
                    FROM sales
                    WHERE date >= DATE_TRUNC('quarter', CURRENT_DATE)
                    GROUP BY country
                ),
                total AS (
                    SELECT SUM(total_revenue) AS global_revenue FROM trimestre
                )
                SELECT t.country,
                       t.total_revenue,
                       t.total_revenue / NULLIF(total.global_revenue,0) AS share_global
                FROM trimestre t, total
                ORDER BY t.total_revenue DESC
                LIMIT 5;
            """
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
