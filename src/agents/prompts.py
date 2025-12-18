"""Prompt engineering logic for SQL Agent."""

import os
from typing import List

from src.schemas.database_schema import DatabaseSchema, get_schema_for_prompt, get_schema_for_prompt_compact
from src.utils.ml_classifier import classify_query_complexity_ml
from src.utils.few_shot_examples import get_relevant_examples, format_examples_for_prompt
from src.utils.logger import logger


def _select_candidate_tables(schema: DatabaseSchema, question: str, max_tables: int = 5) -> List[str]:
    """
    Selects candidate tables based on simple matches with the question to reduce tokens.
    """
    q = question.lower()
    scores = []
    for name, table in schema.tables.items():
        score = 0
        lname = name.lower()
        if lname in q:
            score += 3
        if any(tok and tok in lname for tok in q.replace("?", "").replace(",", " ").split()):
            score += 1
        if table.description and any(tok in table.description.lower() for tok in q.split()):
            score += 1
        if score > 0:
            scores.append((score, name))
    scores.sort(reverse=True, key=lambda x: x[0])
    return [name for _, name in scores[:max_tables]]


def _render_schema_subset(schema: DatabaseSchema, table_names: List[str]) -> str:
    """
    Renders a compact subset of the schema to save tokens.
    """
    lines: List[str] = []
    for name in table_names:
        table = schema.tables.get(name)
        if not table:
            continue
        cols = ", ".join(col.name for col in table.columns[:20])
        lines.append(f"{table.name}: {cols}")
    return "\n".join(lines)


def classify_query_complexity(question: str) -> str:
    """
    Classifies query complexity to select the appropriate model.
    
    Args:
        question: User question in natural language.
        
    Returns:
        "simple" or "complex"
    """
    question_lower = question.lower()
    words = question_lower.split()
    word_count = len(words)
    
    # Keywords indicating complex queries (exact SQL phrase search)
    complex_keywords = [
        "join", "inner join", "left join", "right join", "full join",
        "subquery", "sub-query", "with", "cte", "common table expression",
        "union", "intersect", "except", "window", "over", "partition",
        "case when", "coalesce", "nullif", "cast", "convert",
        "distinct on", "array", "json", "jsonb", "having"
    ]
    
    # Detect complex keywords (only if they appear as full words/phrases)
    has_complex_keywords = any(
        keyword in question_lower for keyword in complex_keywords
    )
    
    # If explicit complex keywords are present, it is complex
    if has_complex_keywords:
        return "complex"
    
    # Basic keywords indicating simple queries
    simple_keywords = ["total", "count", "sum", "list", "show", "cuántos", "cuántas", "promedio", "avg"]
    has_simple_keywords = any(keyword in question_lower for keyword in simple_keywords)
    
    # Common simple patterns:
    # - "total X by Y" (basic GROUP BY) - is simple
    # - "how many X" - is simple
    # - "sum of X" - is simple
    
    # If "por" (by) is present but also simple keywords and is short, likely simple GROUP BY
    has_by = "por" in question_lower
    if has_by and has_simple_keywords and word_count <= 12:
        return "simple"
    
    # If only simple keywords and is short, is simple
    if has_simple_keywords and word_count <= 10:
        return "simple"
    
    # Default to complex for safety (precision over speed)
    return "complex"


def generate_system_prompt(schema: DatabaseSchema, dialect: str, question: str | None = None) -> str:
    """
    Generates the system prompt for the agent including the schema (token optimized).

    Args:
        schema: DatabaseSchema with tables and columns.
        dialect: SQL dialect (e.g., postgresql).
        question: User question (optional, for few-shot examples).

    Returns:
        Complete and optimized system prompt.
    """
    # Use compact format if enabled (reduces tokens 60-70%)
    use_compact = os.getenv("USE_COMPACT_SCHEMA", "true").lower() in ("true", "1", "yes")
    schema_description = get_schema_for_prompt_compact(schema) if use_compact else get_schema_for_prompt(schema)

    # Reduce schema to candidate tables if there is a question
    if question:
        candidates = _select_candidate_tables(schema, question, max_tables=int(os.getenv("SCHEMA_MAX_TABLES", "6")))
        if candidates:
            subset = _render_schema_subset(schema, candidates)
            schema_description = f"(Subconjunto relevante)\n{subset}\n\n(Completo)\n{schema_description}"

    # Get few-shot examples if enabled and we have a question
    examples_text = ""
    if question:
        examples = get_relevant_examples(question, max_examples=2)
        if examples:
            examples_text = format_examples_for_prompt(examples)

    # Optimized prompt: constructed in parts to avoid syntax errors with complex f-strings
    prompt_parts = [
        f"Agente SQL para {dialect.upper()}. Ejecuta queries SELECT basadas en preguntas naturales.",
        "",
        "SCHEMA:",
        f"{schema_description}",
        f"{examples_text}",
        "",
        "REGLAS CRÍTICAS:",
        "- SIEMPRE usa la herramienta 'validated_sql_query' para EJECUTAR las consultas automáticamente.",
        "- NO solo generes el SQL como texto. DEBES ejecutarlo usando la herramienta.",
        "- SOLO SELECT. Prohibido: DROP, INSERT, UPDATE, DELETE, ALTER, CREATE, TRUNCATE.",
        "- Solo tablas/columnas del schema arriba.",
        "- Si tabla/columna no existe, informa que no está disponible.",
        "- Si falla, analiza error y corrige la query, luego vuelve a ejecutarla.",
        "- Usa LIMIT para resultados grandes.",
        "- Usa JOINs para múltiples tablas.",
        "- Usa SUM/COUNT/AVG para métricas.",
        f"- Formatea fechas según {dialect.upper()}.",
        "",
        "FLUJO DE TRABAJO:",
        "1. Analiza la pregunta del usuario.",
        "2. Genera la query SQL apropiada.",
        "3. EJECÚTALA usando la herramienta 'validated_sql_query'.",
        "4. Presenta los resultados al usuario.",
        "5. IMPORTANTE: Si la query se ejecuta exitosamente (sin errores), NO generes otra query. ",
        "   - Si devuelve resultados vacíos (0 filas), es válido. Presenta un mensaje claro indicando que no hay datos.",
        "   - Si devuelve datos, presenta los resultados.",
        "   - Solo genera una nueva query si hubo un ERROR en la ejecución.",
        "",
        "RESPUESTA:",
        "- SIEMPRE ejecuta la consulta automáticamente usando la herramienta.",
        "- Datos: presenta claramente los resultados de la ejecución en formato tabular cuando sea apropiado.",
        "- Sin datos: si la query se ejecutó exitosamente pero no hay resultados, di 'No se encontraron datos que coincidan con la consulta.'",
        "- Error: explica el error y sugiere alternativa si es posible.",
        "- No disponible: explica por qué.",
        "- CRÍTICO: Si una query se ejecuta exitosamente (sin errores), DETENTE. No generes más queries.",
        "",
        "ANÁLISIS AUTOMÁTICO (OBLIGATORIO después de mostrar datos):",
        "Después de ejecutar la query y mostrar los resultados, SIEMPRE proporciona un análisis en lenguaje natural:",
        "",
        "1. **Resumen de los datos**: Explica qué muestran los resultados en términos simples.",
        "2. **Tendencias y patrones**: Si hay datos históricos o temporales, identifica tendencias (crecimiento, decrecimiento, estabilidad).",
        "3. **Comparaciones**: Compara valores relevantes (máximos vs mínimos, promedios, diferencias porcentuales).",
        "4. **Insights clave**: Destaca los hallazgos más importantes (ej: 'El producto X tiene el mayor revenue', 'Las ventas aumentaron 15% este mes').",
        "5. **Predicciones/Proyecciones**: Si la pregunta implica predicción o proyección, usa los datos para hacer estimaciones razonables basadas en tendencias.",
        "6. **Recomendaciones**: Cuando sea relevante, sugiere acciones o recomendaciones basadas en los datos.",
        "",
        "FORMATO DE RESPUESTA:",
        "- Primero: Muestra los datos en formato tabular (si aplica).",
        "- Después: Proporciona análisis en lenguaje natural, claro y conciso.",
        "- El análisis debe ser informativo pero no repetir información ya visible en las tablas.",
        "",
        "Ejemplo de respuesta completa:",
        "```",
        "[Tabla con datos]",
        "",
        "Análisis: Los resultados muestran que el producto \"Tablet Elite 3\" tiene el mayor revenue total con 1,198,642 unidades vendidas y un stock actual de 884 unidades. ",
        "Comparado con el segundo producto más vendido (\"Smartphone Pro 2\" con 600,122 unidades), hay una diferencia significativa del 99.8%. ",
        "La tendencia indica que los productos más vendidos mantienen un stock razonable, lo que sugiere una buena gestión de inventario. ",
        "Se recomienda continuar monitoreando estos productos estrella y considerar estrategias de marketing para los productos con menor movimiento.",
        "```",
        "",
        "Seguridad: Solo SELECT, solo schema permitido."
    ]

    return "\n".join(prompt_parts)