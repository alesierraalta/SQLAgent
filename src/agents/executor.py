"""Agent execution runtime."""

import os
import time
from typing import Any, Dict, Optional, Union

from langchain_core.messages import AIMessage, ToolMessage
from src.agents.parser import parse_streaming_chunk
from src.agents.tools import _SQL_EXECUTION_INFO
from src.utils.logger import logger
from src.utils.performance import record_query_performance
from src.utils.semantic_cache import get_semantic_cached_result, set_semantic_cached_result

def execute_query(
    agent: Any,
    question: str,
    max_retries: int = 3,
    return_metadata: bool = False,
    stream: bool = False,
    stream_callback: Any | None = None,
    prefer_analysis: bool = True,
) -> Union[str, Dict[str, Any]]:
    """
    Executes a natural language question using the agent with retry logic.

    Args:
        agent: LangChain Agent.
        question: Natural language question.
        max_retries: Max retries on error.
        return_metadata: If True, returns dict with response and metadata.
        stream: If True, uses streaming mode.
        stream_callback: Optional callback for real-time streaming info.
        prefer_analysis: If True, prioritizes LLM analysis over raw tool output.

    Returns:
        Agent response (str) or dict with metadata.
    """
    logger.info(f"Executing question: {question}")
    # Clear per-execution state for SQL cache hit detection
    _SQL_EXECUTION_INFO.set(None)

    # 1. Semantic Cache check (only if enabled)
    semantic_cache_result = None
    if os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() in ("true", "1", "yes"):
        try:
            semantic_cache_result = get_semantic_cached_result(question)
            if semantic_cache_result:
                result, sql_generated = semantic_cache_result
                logger.info("Result obtained from semantic cache")
                
                if return_metadata:
                    return {
                        "response": result,
                        "sql_generated": sql_generated,
                        "execution_time": 0.0,
                        "success": True,
                        "cache_hit_type": "semantic",
                    }
                
                return result
        except Exception as e:
            logger.warning(f"Error checking semantic cache: {e}. Continuing...")

    last_error = None
    
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            
            if stream:
                # Streaming mode
                result_messages = []
                current_sql = None
                current_response = None
                
                for chunk in agent.stream({"messages": [{"role": "user", "content": question}]}):
                    # Parse chunk
                    chunk_info = parse_streaming_chunk(chunk, current_sql, current_response)
                    
                    # Update state
                    if chunk_info:
                        if chunk_info.get("sql"):
                            current_sql = chunk_info["sql"]
                        if chunk_info.get("content"):
                            current_response = chunk_info["content"]
                        
                        # Call callback
                        if stream_callback:
                            stream_callback(chunk_info)
                    
                    # Accumulate messages
                    for key, value in chunk.items():
                        if isinstance(value, dict) and "messages" in value:
                            result_messages.extend(value["messages"])
                
                # Construct result similar to invoke
                result = {"messages": result_messages}
            else:
                # Normal mode
                result = agent.invoke({"messages": [{"role": "user", "content": question}]})
            
            elapsed_time = time.time() - start_time

            # Extract generated SQL, response, and tokens
            sql_generated = None
            response = None
            tokens_input = None
            tokens_output = None
            tokens_total = None
            model_used = None
            cache_hit_type = "none"
            
            if "messages" in result:
                messages = result["messages"]
                if messages:
                    # Search for SQL generated
                    for msg in messages:
                        # Capture tokens
                        if hasattr(msg, "response_metadata"):
                            metadata = msg.response_metadata or {}
                            if "token_usage" in metadata:
                                token_usage = metadata["token_usage"]
                                tokens_input = token_usage.get("prompt_tokens")
                                tokens_output = token_usage.get("completion_tokens")
                                tokens_total = token_usage.get("total_tokens")
                        
                        # Capture model
                        if hasattr(msg, "response_metadata"):
                            metadata = msg.response_metadata or {}
                            if "model" in metadata:
                                model_used = metadata["model"]
                        
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                if tool_call.get("name") == "validated_sql_query":
                                    args = tool_call.get("args", {})
                                    sql_generated = args.get("query")
                                    break
                    
                    # Select response: analysis vs data
                    if prefer_analysis:
                        for msg in reversed(messages):
                            if isinstance(msg, AIMessage) and hasattr(msg, "content") and msg.content:
                                has_tool_calls = hasattr(msg, "tool_calls") and msg.tool_calls
                                content = msg.content
                                if not has_tool_calls or (has_tool_calls and len(str(content)) > 100):
                                    content_str = str(content).strip()
                                    is_analysis = (
                                        len(content_str) > 100 and
                                        not content_str.startswith("[") and
                                        not content_str.startswith("(") and
                                        ("análisis" in content_str.lower() or
                                         "conclusión" in content_str.lower() or
                                         "insight" in content_str.lower() or
                                         "recomendación" in content_str.lower() or
                                         len(content_str.split()) > 20)
                                    )
                                    if is_analysis:
                                        response = content_str
                                        logger.info(f"Analysis response found: {len(response)} chars")
                                        break
                    else:
                        for msg in reversed(messages):
                            if isinstance(msg, ToolMessage) and getattr(msg, "content", None):
                                response = msg.content
                                logger.info(f"Tool execution result: {len(str(response))} chars")
                                break
                    
                    # Fallback to ToolMessage if no response yet
                    if not response:
                        for msg in reversed(messages):
                            if isinstance(msg, ToolMessage) and getattr(msg, "content", None):
                                response = msg.content
                                logger.info(f"Tool execution result: {len(str(response))} chars")
                                break
                    
                    # Fallback to any content
                    if not response:
                        for msg in reversed(messages):
                            if hasattr(msg, "content") and msg.content:
                                if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                                    response = msg.content
                                    logger.info(f"Generated response: {len(response)} chars")
                                    break

            # Absolute fallback
            if not response:
                if "messages" in result and result["messages"]:
                    first_msg = result["messages"][0]
                    if hasattr(first_msg, "content") and first_msg.content:
                        response = str(first_msg.content)
                    else:
                        response = str(result)
                else:
                    response = str(result)

            # Adjust SQL/cache info from context
            exec_info = _SQL_EXECUTION_INFO.get()
            if exec_info:
                executed_sql, was_sql_cache_hit = exec_info
                if executed_sql:
                    sql_generated = executed_sql
                if was_sql_cache_hit:
                    cache_hit_type = "sql"

            # Save to semantic cache if successful
            if sql_generated and response and not response.startswith("Error"):
                try:
                    set_semantic_cached_result(question, response, sql_generated)
                except Exception as cache_error:
                    logger.warning(f"Error saving to semantic cache: {cache_error}")

            # Record performance metrics
            if sql_generated and sql_generated.strip():
                try:
                    rows_returned = None
                    if response and not response.startswith("Error"):
                        try:
                            import ast
                            parsed = ast.literal_eval(response.strip())
                            if isinstance(parsed, list):
                                rows_returned = len(parsed)
                        except:
                            pass
                    
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
                    logger.warning(f"Error recording performance metrics: {perf_error}")
            
            # Format empty response
            response_str = str(response).strip() if response else ""
            is_empty_response = (
                not response_str or 
                response_str == "[]" or 
                response_str == ""
            )
            
            if is_empty_response and sql_generated and not response.startswith("Error"):
                formatted_response = "No se encontraron datos que coincidan con la consulta."
                logger.info("Empty response detected but query successful. Formatting message.")
                response = formatted_response
            
            if return_metadata:
                return {
                    "response": response,
                    "sql_generated": sql_generated,
                    "execution_time": elapsed_time,
                    "success": response and not response.startswith("Error"),
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                    "tokens_total": tokens_total,
                    "cache_hit_type": cache_hit_type,
                    "model_used": model_used,
                }
            
            return response

        except Exception as e:
            last_error = e
            wait_time = 2 ** attempt
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                f"Retrying in {wait_time}s..."
            )
            if attempt < max_retries - 1:
                time.sleep(wait_time)

    error_msg = f"Error al ejecutar query después de {max_retries} intentos: {str(last_error)}"
    logger.error(error_msg)
    return error_msg