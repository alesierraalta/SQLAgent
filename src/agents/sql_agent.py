"""Agente LangChain para generaci?n y ejecuci?n de queries SQL con validaci?n."""

import os
import time
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool as tool_decorator
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import Engine

from src.agents.error_recovery import recover_from_error, should_attempt_recovery
from src.schemas.database_schema import DatabaseSchema, get_schema_for_prompt, get_schema_for_prompt_compact
from src.utils.ml_classifier import classify_query_complexity_ml
from src.utils.cache import get_cached_result, set_cached_result
from src.utils.telemetry import record_query_metrics, record_token_usage
from src.utils.few_shot_examples import get_relevant_examples, format_examples_for_prompt
from src.utils.logger import logger
from src.utils.semantic_cache import get_semantic_cached_result, set_semantic_cached_result
from src.validators.sql_validator import SQLValidator

# Cargar variables de entorno
load_dotenv()


def _classify_query_complexity(question: str) -> str:
    """
    Clasifica la complejidad de una query para seleccionar el modelo apropiado.
    
    Args:
        question: Pregunta del usuario en lenguaje natural
        
    Returns:
        "simple" o "complex"
    """
    question_lower = question.lower()
    words = question_lower.split()
    word_count = len(words)
    
    # Keywords que indican queries complejas (búsqueda exacta de frases SQL)
    complex_keywords = [
        "join", "inner join", "left join", "right join", "full join",
        "subquery", "sub-query", "with", "cte", "common table expression",
        "union", "intersect", "except", "window", "over", "partition",
        "case when", "coalesce", "nullif", "cast", "convert",
        "distinct on", "array", "json", "jsonb", "having"
    ]
    
    # Detectar keywords complejos (solo si aparecen como palabras completas)
    has_complex_keywords = any(
        keyword in question_lower for keyword in complex_keywords
    )
    
    # Si tiene keywords complejos explícitos, es compleja
    if has_complex_keywords:
        return "complex"
    
    # Keywords básicos que indican queries simples
    simple_keywords = ["total", "count", "sum", "list", "show", "cuántos", "cuántas", "promedio", "avg"]
    has_simple_keywords = any(keyword in question_lower for keyword in simple_keywords)
    
    # Patrones simples comunes:
    # - "total X por Y" (GROUP BY básico) - es simple
    # - "cuántos X" - es simple
    # - "suma de X" - es simple
    
    # Si tiene "por" pero también tiene keywords simples y es corta, probablemente es simple GROUP BY
    has_por = "por" in question_lower
    if has_por and has_simple_keywords and word_count <= 12:
        # "total X por Y" es un GROUP BY simple, no complejo
        return "simple"
    
    # Si solo tiene keywords simples y es corta, es simple
    if has_simple_keywords and word_count <= 10:
        return "simple"
    
    # Si es muy corta (<=6 palabras) y tiene keywords simples, es simple
    if word_count <= 6 and has_simple_keywords:
        return "simple"
    
    # Por defecto, asumir compleja para seguridad (mejor precisión que velocidad)
    return "complex"


def create_sql_agent(engine: Engine, schema: DatabaseSchema, llm: ChatOpenAI | None = None, question: str | None = None) -> Any:
    """
    Crea un agente LangChain para consultas SQL con validaci?n estricta.

    Args:
        engine: SQLAlchemy Engine con conexi?n a la base de datos
        schema: DatabaseSchema con las tablas y columnas permitidas
        llm: Modelo LLM (opcional, usa gpt-4o por defecto)

    Returns:
        Agente LangChain configurado
    """
    # Inicializar LLM si no se proporciona
    if llm is None:
        # Model selection inteligente: usar gpt-4o-mini para queries simples
        use_fast_model = os.getenv("USE_FAST_MODEL", "true").lower() in ("true", "1", "yes")
        fast_model = os.getenv("FAST_MODEL", "gpt-4o-mini")
        complex_model = os.getenv("COMPLEX_MODEL", "gpt-4o")
        default_model = os.getenv("OPENAI_MODEL", "gpt-4o")
        
        if use_fast_model and question:
            # FASE E: Usar clasificador ML mejorado
            complexity = classify_query_complexity_ml(question)
            if complexity == "simple":
                model_name = fast_model
                logger.info(
                    f"Model Selection: Query clasificada como 'simple' "
                    f"(palabras: {len(question.split())}), usando modelo rápido: {model_name}"
                )
            else:
                model_name = complex_model
                logger.info(
                    f"Model Selection: Query clasificada como 'complex' "
                    f"(palabras: {len(question.split())}), usando modelo completo: {model_name}"
                )
        else:
            model_name = default_model
            if question:
                logger.info(f"Model Selection: Usando modelo por defecto: {model_name} (USE_FAST_MODEL=false o sin question)")
            else:
                logger.info(f"Model Selection: Usando modelo por defecto: {model_name} (sin question para clasificación)")
        
        # Configurar prompt caching si est? habilitado
        # OpenAI cachea autom?ticamente prefijos >1024 tokens
        # El schema + reglas deber?an ser >1024 tokens para aprovechar caching
        llm_kwargs = {
            "model": model_name,
            "temperature": 0,
            "max_tokens": None,
        }
        
        # Intentar habilitar prompt caching si est? disponible y habilitado
        enable_prompt_caching = os.getenv("ENABLE_PROMPT_CACHING", "true").lower() in ("true", "1", "yes")
        if enable_prompt_caching:
            # Nota: LangChain puede no exponer cache_control directamente
            # OpenAI API soporta prompt caching autom?tico para prefijos >1024 tokens
            # Aseguramos que el prefijo (schema + reglas) sea consistente
            logger.debug("Prompt caching habilitado (requiere prefijo >1024 tokens)")
        
        llm = ChatOpenAI(**llm_kwargs)

    # Crear SQLDatabase wrapper
    db = SQLDatabase(engine)

    # Crear toolkit
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    # Obtener herramientas del toolkit
    tools = toolkit.get_tools()

    # Crear validador
    validator = SQLValidator(schema)

    # Buscar la herramienta sql_db_query del toolkit antes de definir la funci?n
    sql_db_query_tool = None
    for t in tools:
        if t.name == "sql_db_query":
            sql_db_query_tool = t
            break

    if sql_db_query_tool is None:
        raise ValueError("No se encontr? la herramienta sql_db_query en el toolkit")

    # Crear custom tool con validaci?n
    @tool_decorator
    def validated_sql_query(query: str) -> str:
        """
        Ejecuta una query SQL despu?s de validarla contra el schema.

        Esta herramienta valida que:
        - Solo se usen comandos SELECT
        - Solo se acceda a tablas y columnas permitidas
        - No se ejecuten comandos peligrosos (DROP, INSERT, UPDATE, etc.)

        Args:
            query: Query SQL a ejecutar

        Returns:
            Resultado de la query o mensaje de error
        """
        try:
            # Validar query
            validator.validate_query(query)
            logger.info(f"Query validada exitosamente: {query[:100]}...")

            # Verificar SQL cache antes de ejecutar (más rápido que semantic cache)
            cached_result = get_cached_result(query)
            if cached_result is not None:
                logger.info("Resultado obtenido del SQL cache")
                return cached_result

            # Ejecutar query con timeout
            query_timeout = int(os.getenv("QUERY_TIMEOUT", "30"))
            start_time = time.time()

            try:
                # Ejecutar query usando la herramienta del toolkit (ya tiene manejo de errores)
                # sql_db_query_tool est? capturado del closure
                result = sql_db_query_tool.invoke({"query": query})
                elapsed = time.time() - start_time

                # Convertir resultado a string para verificar si está vacío
                result_str = str(result).strip()
                
                logger.info(
                    f"Query ejecutada exitosamente en {elapsed:.2f}s. "
                    f"Resultados: {len(result_str)} caracteres"
                )
                
                # Si el resultado está vacío, formatear mensaje apropiado
                if not result_str or result_str == "[]" or result_str == "":
                    formatted_result = "No se encontraron datos que coincidan con la consulta."
                    logger.info("Query ejecutada exitosamente pero sin resultados. Retornando mensaje formateado.")
                    # Guardar mensaje formateado en cache
                    set_cached_result(query, formatted_result)
                else:
                    formatted_result = result
                    # Guardar en cache
                    set_cached_result(query, result)
                
                # FASE F: Registrar métricas de telemetría
                record_query_metrics(
                    duration=elapsed,
                    success=True,
                    complexity="unknown",  # Se registra después con más contexto
                    cache_hit=False
                )
                
                return formatted_result

            except Exception as db_error:
                elapsed = time.time() - start_time
                error_msg = str(db_error)
                
                # Intentar recuperaci?n autom?tica si es apropiado
                if should_attempt_recovery(error_msg):
                    logger.info("Intentando recuperaci?n autom?tica del error...")
                    try:
                        # Obtener informaci?n del schema para la recuperaci?n
                        schema_info = get_schema_for_prompt(schema)
                        
                        # Generar query corregida
                        corrected_sql = recover_from_error(query, error_msg, schema_info)
                        
                        if corrected_sql and corrected_sql != query:
                            logger.info(f"Query corregida generada: {corrected_sql[:100]}...")
                            
                            # Validar la query corregida antes de ejecutarla
                            try:
                                validator.validate_query(corrected_sql)
                                
                                # Ejecutar query corregida
                                start_time_corrected = time.time()
                                result = sql_db_query_tool.invoke({"query": corrected_sql})
                                elapsed_corrected = time.time() - start_time_corrected
                                
                                # Convertir resultado a string para verificar si está vacío
                                result_str = str(result).strip()
                                
                                logger.info(
                                    f"Query corregida ejecutada exitosamente en {elapsed_corrected:.2f}s. "
                                    f"Resultados: {len(result_str)} caracteres"
                                )
                                
                                # Si el resultado está vacío, formatear mensaje apropiado
                                if not result_str or result_str == "[]" or result_str == "":
                                    formatted_result = "No se encontraron datos que coincidan con la consulta."
                                    logger.info("Query corregida ejecutada exitosamente pero sin resultados. Retornando mensaje formateado.")
                                    set_cached_result(corrected_sql, formatted_result)
                                    return formatted_result
                                else:
                                    # Guardar en cache
                                    set_cached_result(corrected_sql, result)
                                

                                # FASE D: Reportar corrección exitosa para aprendizaje

                                from src.agents.error_recovery import report_successful_correction

                                report_successful_correction(

                                    original_sql=query,

                                    error_message=error_msg,

                                    corrected_sql=corrected_sql

                                )

                                
                                return result
                                
                            except Exception as validation_error:
                                logger.warning(
                                    f"Query corregida no pas? validaci?n: {validation_error}. "
                                    f"Retornando error original."
                                )
                        else:
                            logger.warning("No se pudo generar una query corregida v?lida")
                            
                    except Exception as recovery_error:
                        logger.warning(f"Error durante recuperaci?n autom?tica: {recovery_error}")
                
                # Si no se pudo recuperar, retornar error original
                final_error_msg = f"Error al ejecutar query en BD (despu?s de {elapsed:.2f}s): {error_msg}"
                logger.error(final_error_msg)
                return final_error_msg

        except Exception as e:
            error_msg = f"Error al ejecutar query: {str(e)}"
            logger.error(f"{error_msg}. Query: {query[:100]}...")
            return error_msg

    # Reemplazar sql_db_query con nuestra versi?n validada
    validated_tools = []
    for tool in tools:
        if tool.name == "sql_db_query":
            validated_tools.append(validated_sql_query)
        else:
            validated_tools.append(tool)

    # Generar system prompt din?mico (con ejemplos few-shot si est?n disponibles)
    system_prompt = _generate_system_prompt(schema, db.dialect, question=question)

    # Configurar LLM con tool_choice para forzar ejecuci?n de herramientas
    # tool_choice="any" fuerza al modelo a usar al menos una herramienta cuando sea apropiado
    llm_with_tools = llm.bind_tools(validated_tools, tool_choice="any")

    # Crear agente con LLM configurado para forzar tool execution
    agent = create_agent(
        llm_with_tools,  # Usar LLM con tools bound y tool_choice
        validated_tools,
        system_prompt=system_prompt,
    )

    logger.info("Agente SQL creado exitosamente")
    return agent


def _generate_system_prompt(schema: DatabaseSchema, dialect: str, question: str | None = None) -> str:
    """
    Genera el system prompt para el agente incluyendo el schema (optimizado para tokens).

    Args:
        schema: DatabaseSchema con las tablas y columnas
        dialect: Dialecto SQL (ej: postgresql)
        question: Pregunta del usuario (opcional, para few-shot examples)

    Returns:
        System prompt completo y optimizado
    """
    # Usar formato compacto si está habilitado (reduce tokens 60-70%)
    use_compact = os.getenv("USE_COMPACT_SCHEMA", "true").lower() in ("true", "1", "yes")
    if use_compact:
        schema_description = get_schema_for_prompt_compact(schema)
    else:
        schema_description = get_schema_for_prompt(schema)

    # Obtener ejemplos few-shot si están habilitados y tenemos una pregunta
    examples_text = ""
    if question:
        examples = get_relevant_examples(question, max_examples=2)
        if examples:
            examples_text = format_examples_for_prompt(examples)

    # Prompt optimizado: más conciso para reducir tokens
    prompt = f"""Agente SQL para {dialect.upper()}. Ejecuta queries SELECT basadas en preguntas naturales.

SCHEMA:
{schema_description}
{examples_text}

REGLAS CRÍTICAS:
- SIEMPRE usa la herramienta 'validated_sql_query' para EJECUTAR las consultas automáticamente.
- NO solo generes el SQL como texto. DEBES ejecutarlo usando la herramienta.
- SOLO SELECT. Prohibido: DROP, INSERT, UPDATE, DELETE, ALTER, CREATE, TRUNCATE.
- Solo tablas/columnas del schema arriba.
- Si tabla/columna no existe, informa que no está disponible.
- Si falla, analiza error y corrige la query, luego vuelve a ejecutarla.
- Usa LIMIT para resultados grandes.
- Usa JOINs para múltiples tablas.
- Usa SUM/COUNT/AVG para métricas.
- Formatea fechas según {dialect.upper()}.

FLUJO DE TRABAJO:
1. Analiza la pregunta del usuario.
2. Genera la query SQL apropiada.
3. EJECÚTALA usando la herramienta 'validated_sql_query'.
4. Presenta los resultados al usuario.
5. IMPORTANTE: Si la query se ejecuta exitosamente (sin errores), NO generes otra query. 
   - Si devuelve resultados vacíos (0 filas), es válido. Presenta un mensaje claro indicando que no hay datos.
   - Si devuelve datos, presenta los resultados.
   - Solo genera una nueva query si hubo un ERROR en la ejecución.

RESPUESTA:
- SIEMPRE ejecuta la consulta automáticamente usando la herramienta.
- Datos: presenta claramente los resultados de la ejecución en formato tabular cuando sea apropiado.
- Sin datos: si la query se ejecutó exitosamente pero no hay resultados, di "No se encontraron datos que coincidan con la consulta."
- Error: explica el error y sugiere alternativa si es posible.
- No disponible: explica por qué.
- CRÍTICO: Si una query se ejecuta exitosamente (sin errores), DETENTE. No generes más queries.

ANÁLISIS AUTOMÁTICO (OBLIGATORIO después de mostrar datos):
Después de ejecutar la query y mostrar los resultados, SIEMPRE proporciona un análisis en lenguaje natural:

1. **Resumen de los datos**: Explica qué muestran los resultados en términos simples.
2. **Tendencias y patrones**: Si hay datos históricos o temporales, identifica tendencias (crecimiento, decrecimiento, estabilidad).
3. **Comparaciones**: Compara valores relevantes (máximos vs mínimos, promedios, diferencias porcentuales).
4. **Insights clave**: Destaca los hallazgos más importantes (ej: "El producto X tiene el mayor revenue", "Las ventas aumentaron 15% este mes").
5. **Predicciones/Proyecciones**: Si la pregunta implica predicción o proyección, usa los datos para hacer estimaciones razonables basadas en tendencias.
6. **Recomendaciones**: Cuando sea relevante, sugiere acciones o recomendaciones basadas en los datos.

FORMATO DE RESPUESTA:
- Primero: Muestra los datos en formato tabular (si aplica).
- Después: Proporciona análisis en lenguaje natural, claro y conciso.
- El análisis debe ser informativo pero no repetir información ya visible en las tablas.

Ejemplo de respuesta completa:
```
[Tabla con datos]

Análisis: Los resultados muestran que el producto "Tablet Elite 3" tiene el mayor revenue total con 1,198,642 unidades vendidas y un stock actual de 884 unidades. 
Comparado con el segundo producto más vendido ("Smartphone Pro 2" con 600,122 unidades), hay una diferencia significativa del 99.8%. 
La tendencia indica que los productos más vendidos mantienen un stock razonable, lo que sugiere una buena gestión de inventario. 
Se recomienda continuar monitoreando estos productos estrella y considerar estrategias de marketing para los productos con menor movimiento.
```

Seguridad: Solo SELECT, solo schema permitido."""

    return prompt


def _parse_streaming_chunk(chunk: dict, current_sql: str | None = None, current_response: str | None = None) -> dict | None:
    """
    Parsea un chunk del streaming del agente para extraer información relevante.
    
    Args:
        chunk: Chunk del stream del agente
        current_sql: SQL actualmente detectado (para tracking)
        current_response: Respuesta actual (para tracking)
        
    Returns:
        Dict con información del chunk o None si no hay información relevante.
        Keys: 'type' (sql|execution|data|analysis|error), 'content', 'sql', 'complete'
    """
    try:
        from langchain_core.messages import AIMessage, ToolMessage
        
        chunk_info = {}
        
        # Buscar mensajes en el chunk
        for key, value in chunk.items():
            if isinstance(value, dict) and "messages" in value:
                messages = value["messages"]
                
                for msg in messages:
                    # Detectar SQL generado en AIMessage con tool_calls
                    if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            if tool_call.get("name") == "validated_sql_query":
                                args = tool_call.get("args", {})
                                sql = args.get("query")
                                if sql and sql != current_sql:
                                    chunk_info.update({
                                        "type": "sql",
                                        "sql": sql,
                                        "content": sql,
                                        "complete": True
                                    })
                                    return chunk_info
                    
                    # Detectar resultados de ejecución en ToolMessage
                    if isinstance(msg, ToolMessage):
                        content = getattr(msg, "content", None) or str(msg)
                        if content and content != current_response:
                            # Detectar si es error
                            if "Error" in content or "error" in content.lower():
                                chunk_info.update({
                                    "type": "error",
                                    "content": content,
                                    "complete": True
                                })
                            else:
                                # Es resultado de ejecución
                                chunk_info.update({
                                    "type": "execution",
                                    "content": content,
                                    "complete": True
                                })
                            return chunk_info
                    
                    # Detectar respuesta final del agente (análisis)
                    if isinstance(msg, AIMessage) and hasattr(msg, "content") and msg.content:
                        content = msg.content
                        # Si no es un tool call y tiene contenido, es análisis/respuesta
                        if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                            # Verificar si es contenido nuevo (no solo SQL)
                            if content and len(content) > 50:  # Respuestas significativas
                                chunk_info.update({
                                    "type": "analysis",
                                    "content": content,
                                    "complete": False  # Puede seguir generándose
                                })
                                return chunk_info
        
        # Si hay contenido parcial en el chunk pero no es un mensaje completo
        if "agent" in chunk:
            agent_chunk = chunk["agent"]
            if isinstance(agent_chunk, dict) and "messages" in agent_chunk:
                for msg in agent_chunk["messages"]:
                    if hasattr(msg, "content") and msg.content:
                        content = msg.content
                        # Contenido parcial de análisis
                        if len(content) > 10:
                            chunk_info.update({
                                "type": "analysis",
                                "content": content,
                                "complete": False
                            })
                            return chunk_info
        
        return None
        
    except Exception as e:
        logger.debug(f"Error parseando chunk de streaming: {e}")
        return None


def execute_query(
    agent: Any,
    question: str,
    max_retries: int = 3,
    return_metadata: bool = False,
    stream: bool = False,
    stream_callback: Any | None = None,
) -> str | dict[str, Any]:
    """
    Ejecuta una pregunta en lenguaje natural usando el agente con retry logic.

    Args:
        agent: Agente LangChain
        question: Pregunta en lenguaje natural
        max_retries: N?mero m?ximo de reintentos en caso de error
        return_metadata: Si True, retorna dict con respuesta y metadata (SQL generado, tiempo, etc.)
        stream: Si True, usa streaming mode
        stream_callback: Callback opcional para recibir información de streaming en tiempo real.
                        Recibe dict con keys: 'type' (sql|execution|data|analysis|error), 
                        'content' (contenido del chunk), 'complete' (bool)

    Returns:
        Respuesta del agente (str) o dict con respuesta y metadata si return_metadata=True
    """
    logger.info(f"Ejecutando pregunta: {question}")

    # Estrategia optimizada de cache: SQL cache primero (más rápido), luego semantic cache
    # Nota: Para la primera query no tenemos SQL, así que semantic cache tiene sentido
    # Pero intentamos predecir el SQL probable para verificar SQL cache primero
    
    # 1. Intentar semantic cache solo si está habilitado y modelo está cargado
    # (Para queries similares que no tienen SQL exacto)
    semantic_cache_result = None
    if os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() in ("true", "1", "yes"):
        try:
            semantic_cache_result = get_semantic_cached_result(question)
            if semantic_cache_result:
                result, sql_generated = semantic_cache_result
                logger.info("Resultado obtenido del semantic cache")
                
                # Registrar métricas si se solicita
                if return_metadata:
                    return {
                        "response": result,
                        "sql_generated": sql_generated,
                        "execution_time": 0.0,  # Cache hit = tiempo instantáneo
                        "success": True,
                        "cache_hit_type": "semantic",
                    }
                
                return result
        except Exception as e:
            logger.warning(f"Error al verificar semantic cache: {e}. Continuando...")

    last_error = None
    # Detectar loops: rastrear queries ejecutadas y resultados vacíos repetidos
    executed_queries = []
    empty_results_count = 0
    max_empty_results = 3  # Máximo de resultados vacíos antes de detener
    
    for attempt in range(max_retries):
        try:
            # Ejecutar agente (con streaming si se solicita)
            start_time = time.time()
            
            if stream:
                # Streaming mode: usar agent.stream() y acumular resultados
                result_messages = []
                current_sql = None
                current_response = None
                
                for chunk in agent.stream({"messages": [{"role": "user", "content": question}]}):
                    # Parsear chunk para extraer información y llamar callback
                    chunk_info = _parse_streaming_chunk(chunk, current_sql, current_response)
                    
                    # Actualizar estado actual
                    if chunk_info.get("sql"):
                        current_sql = chunk_info["sql"]
                    if chunk_info.get("content"):
                        current_response = chunk_info["content"]
                    
                    # Llamar callback si está disponible
                    if stream_callback and chunk_info:
                        stream_callback(chunk_info)
                    
                    # Acumular mensajes de todos los chunks
                    for key, value in chunk.items():
                        if isinstance(value, dict) and "messages" in value:
                            result_messages.extend(value["messages"])
                
                # Construir resultado similar a invoke
                result = {"messages": result_messages}
            else:
                # Normal mode: usar agent.invoke()
                result = agent.invoke({"messages": [{"role": "user", "content": question}]})
            
            elapsed_time = time.time() - start_time

            # Extraer SQL generado, respuesta, y tokens
            sql_generated = None
            response = None
            tokens_input = None
            tokens_output = None
            tokens_total = None
            model_used = None
            
            if "messages" in result:
                messages = result["messages"]
                if messages:
                    # Buscar SQL generado en AIMessage con tool_calls
                    for msg in messages:
                        # Capturar tokens si están disponibles
                        if hasattr(msg, "response_metadata"):
                            metadata = msg.response_metadata or {}
                            if "token_usage" in metadata:
                                token_usage = metadata["token_usage"]
                                tokens_input = token_usage.get("prompt_tokens")
                                tokens_output = token_usage.get("completion_tokens")
                                tokens_total = token_usage.get("total_tokens")
                        
                        # Capturar modelo usado
                        if hasattr(msg, "response_metadata"):
                            metadata = msg.response_metadata or {}
                            if "model" in metadata:
                                model_used = metadata["model"]
                        
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                if tool_call.get("name") == "validated_sql_query":
                                    # Extraer SQL del argumento de la tool call
                                    args = tool_call.get("args", {})
                                    sql_generated = args.get("query")
                                    break
                    
                    # Priorizar AIMessage con análisis sobre ToolMessage (solo datos)
                    # Buscar primero AIMessage que tenga contenido analítico (no solo tool calls)
                    from langchain_core.messages import AIMessage
                    
                    for msg in reversed(messages):
                        if isinstance(msg, AIMessage) and hasattr(msg, "content") and msg.content:
                            # Verificar que no sea solo un tool call
                            has_tool_calls = hasattr(msg, "tool_calls") and msg.tool_calls
                            content = msg.content
                            
                            # Si tiene contenido y no es solo un tool call, verificar si tiene análisis
                            if not has_tool_calls or (has_tool_calls and len(str(content)) > 100):
                                # Verificar si el contenido parece ser análisis (más que solo datos)
                                content_str = str(content).strip()
                                is_analysis = (
                                    len(content_str) > 100 and  # Contenido significativo
                                    not content_str.startswith("[") and  # No es solo una lista
                                    not content_str.startswith("(") and  # No es solo una tupla
                                    ("análisis" in content_str.lower() or
                                     "conclusión" in content_str.lower() or
                                     "insight" in content_str.lower() or
                                     "recomendación" in content_str.lower() or
                                     len(content_str.split()) > 20)  # Texto sustancial
                                )
                                
                                if is_analysis:
                                    response = content_str
                                    logger.info(f"Respuesta con análisis encontrada: {len(response)} caracteres")
                                    break
                    
                    # Si no hay AIMessage con análisis, buscar ToolMessage con datos
                    if not response:
                        for msg in reversed(messages):
                            if isinstance(msg, ToolMessage):
                                # ToolMessage contiene el resultado de la ejecuci?n de la herramienta
                                if msg.content:
                                    response = msg.content
                                    logger.info(
                                        f"Resultado de herramienta ejecutada: {len(response)} caracteres"
                                    )
                                    break
                    
                    # Si aún no hay respuesta, buscar cualquier mensaje con contenido
                    if not response:
                        for msg in reversed(messages):
                            if hasattr(msg, "content") and msg.content:
                                # Evitar mensajes que son solo tool calls sin resultados
                                if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                                    response = msg.content
                                    logger.info(f"Respuesta generada: {len(response)} caracteres")
                                    break

            # Si no se encontr? respuesta, usar fallback
            if not response:
                response = str(result)

            # Detectar loops: verificar si estamos generando queries repetidamente con resultados vacíos
            if sql_generated:
                # Normalizar SQL para comparación (remover espacios extras, convertir a minúsculas)
                normalized_sql = " ".join(sql_generated.strip().lower().split())
                
                # Verificar si esta query ya fue ejecutada
                if normalized_sql in executed_queries:
                    logger.warning(
                        f"Query duplicada detectada. El agente está generando la misma query repetidamente. "
                        f"Deteniendo para evitar loop infinito."
                    )
                    # Si ya tenemos una respuesta (aunque esté vacía), retornarla
                    if response:
                        return response
                    # Si no hay respuesta, retornar mensaje apropiado
                    return "No se encontraron datos que coincidan con la consulta."
                
                # Agregar query a la lista de ejecutadas
                executed_queries.append(normalized_sql)
                
                # Verificar si el resultado está vacío
                response_str = str(response).strip() if response else ""
                is_empty = (
                    not response_str or 
                    response_str == "[]" or 
                    response_str == "" or
                    response_str == "No se encontraron datos que coincidan con la consulta."
                )
                
                if is_empty and not response.startswith("Error"):
                    empty_results_count += 1
                    logger.info(
                        f"Resultado vacío detectado ({empty_results_count}/{max_empty_results}). "
                        f"Si se alcanza el límite, se detendrá el agente."
                    )
                    
                    # Si hemos tenido demasiados resultados vacíos, detener
                    if empty_results_count >= max_empty_results:
                        logger.warning(
                            f"Se detectaron {max_empty_results} resultados vacíos consecutivos. "
                            f"Deteniendo agente para evitar loop infinito."
                        )
                        return "No se encontraron datos que coincidan con la consulta."
                else:
                    # Resetear contador si hay resultados o errores
                    empty_results_count = 0

            # Guardar en semantic cache si la query fue exitosa
            if sql_generated and response and not response.startswith("Error"):
                try:
                    set_semantic_cached_result(question, response, sql_generated)
                except Exception as cache_error:
                    logger.warning(f"Error al guardar en semantic cache: {cache_error}")

            # Registrar m?tricas de performance si tenemos SQL
            if sql_generated and sql_generated.strip():
                try:
                    from src.utils.performance import record_query_performance
                    # Intentar contar filas si la respuesta es una lista de tuplas
                    rows_returned = None
                    if response and not response.startswith("Error"):
                        try:
                            import ast
                            parsed = ast.literal_eval(response.strip())
                            if isinstance(parsed, list):
                                rows_returned = len(parsed)
                        except:
                            pass
                    
                    # Determinar cache hit type
                    cache_hit_type = "none"
                    if semantic_cache_result:
                        cache_hit_type = "semantic"
                    elif sql_generated:
                        # Verificar si fue cache hit de SQL cache
                        from src.utils.cache import get_cached_result
                        cached = get_cached_result(sql_generated)
                        if cached is not None:
                            cache_hit_type = "sql"
                    
                    record_query_performance(
                        sql=sql_generated,
                        execution_time=elapsed_time,
                        success=response and not response.startswith("Error"),
                        error_message=response if response and response.startswith("Error") else None,
                        rows_returned=rows_returned,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        tokens_total=tokens_total,
                        cache_hit_type=cache_hit_type,
                        model_used=model_used,
                    )
                except Exception as perf_error:
                    logger.warning(f"Error al registrar m?tricas de performance: {perf_error}")
            
            # Formatear respuesta vacía apropiadamente si es necesario
            response_str = str(response).strip() if response else ""
            is_empty_response = (
                not response_str or 
                response_str == "[]" or 
                response_str == ""
            )
            
            # Si la respuesta está vacía pero la query fue exitosa (sin errores), formatear mensaje
            if is_empty_response and sql_generated and not response.startswith("Error"):
                formatted_response = "No se encontraron datos que coincidan con la consulta."
                logger.info("Respuesta vacía detectada pero query exitosa. Formateando mensaje apropiado.")
                response = formatted_response
            
            # Retornar con metadata si se solicita
            if return_metadata:
                return {
                    "response": response,
                    "sql_generated": sql_generated,
                    "execution_time": elapsed_time,
                    "success": response and not response.startswith("Error"),
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                    "tokens_total": tokens_total,
                    "cache_hit_type": cache_hit_type if 'cache_hit_type' in locals() else "none",
                    "model_used": model_used,
                }
            
            return response

        except Exception as e:
            last_error = e
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            logger.warning(
                f"Intento {attempt + 1}/{max_retries} fall?: {str(e)}. "
                f"Reintentando en {wait_time}s..."
            )
            if attempt < max_retries - 1:
                time.sleep(wait_time)

    # Si todos los intentos fallaron
    error_msg = f"Error al ejecutar query despu?s de {max_retries} intentos: {str(last_error)}"
    logger.error(error_msg)
    return error_msg
