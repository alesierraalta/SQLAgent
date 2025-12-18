"""Tool definitions and factories for SQL Agent."""

import os
import time
from contextvars import ContextVar
from typing import Optional, Tuple

from langchain.tools import tool as tool_decorator, BaseTool
from src.utils.logger import logger
from src.utils.cache import get_cached_result, set_cached_result
from src.utils.telemetry import record_query_metrics
from src.agents.error_recovery import recover_from_error, should_attempt_recovery, report_successful_correction
from src.schemas.database_schema import get_schema_for_prompt
from src.validators.sql_validator import SQLValidator

# Context variable to track SQL execution info across the request
_SQL_EXECUTION_INFO: ContextVar[Optional[Tuple[str, bool]]] = ContextVar(
    "_SQL_EXECUTION_INFO",
    default=None,
)

def create_validated_sql_tool(schema, validator: SQLValidator, raw_sql_tool: BaseTool) -> BaseTool:
    """
    Creates a custom tool with SQL validation.

    This tool validates that:
    - Only SELECT commands are used
    - Only allowed tables and columns are accessed
    - No dangerous commands (DROP, INSERT, UPDATE, etc.) are executed

    Args:
        schema: DatabaseSchema schema object
        validator: SQLValidator instance
        raw_sql_tool: The raw langchain sql_db_query tool

    Returns:
        Validated tool function decorated as a LangChain tool
    """

    @tool_decorator
    def validated_sql_query(query: str) -> str:
        """
        Executes a SQL query after validating it against the schema.

        Args:
            query: SQL query to execute

        Returns:
            Query result or error message
        """
        try:
            # Validate query
            validator.validate_query(query)
            logger.info(f"Query validated successfully: {query[:100]}...")

            # Check SQL cache before executing (faster than semantic cache)
            cached_result = get_cached_result(query)
            if cached_result is not None:
                logger.info("Result obtained from SQL cache")
                _SQL_EXECUTION_INFO.set((query, True))
                return cached_result

            # Execute query with timeout
            # Note: QUERY_TIMEOUT env var reading is moved inside here or passed? 
            # It's better to read env var here to keep it dynamic.
            start_time = time.time()

            try:
                # Execute query using the toolkit tool (already has error handling)
                result = raw_sql_tool.invoke({"query": query})
                elapsed = time.time() - start_time

                # Convert result to string to check if empty
                result_str = str(result).strip()
                
                logger.info(
                    f"Query executed successfully in {elapsed:.2f}s. "
                    f"Results: {len(result_str)} characters"
                )
                
                # If result is empty, format appropriate message
                if not result_str or result_str == "[]" or result_str == "":
                    formatted_result = "No se encontraron datos que coincidan con la consulta."
                    logger.info("Query executed successfully but with no results. Returning formatted message.")
                    # Save formatted message to cache
                    set_cached_result(query, formatted_result)
                else:
                    formatted_result = result
                    # Save to cache
                    set_cached_result(query, result)
                
                # Record telemetry metrics
                record_query_metrics(
                    duration=elapsed,
                    success=True,
                    complexity="unknown",  # Recorded later with more context
                    cache_hit=False
                )
                
                _SQL_EXECUTION_INFO.set((query, False))
                return formatted_result

            except Exception as db_error:
                elapsed = time.time() - start_time
                error_msg = str(db_error)
                
                # Attempt automatic recovery if appropriate
                if should_attempt_recovery(error_msg):
                    logger.info("Attempting automatic error recovery...")
                    try:
                        # Get schema info for recovery
                        schema_info = get_schema_for_prompt(schema)
                        
                        # Generate corrected query
                        corrected_sql = recover_from_error(query, error_msg, schema_info)
                        
                        if corrected_sql and corrected_sql != query:
                            logger.info(f"Corrected query generated: {corrected_sql[:100]}...")
                            
                            # Validate corrected query before executing
                            try:
                                validator.validate_query(corrected_sql)
                                
                                # Execute corrected query
                                start_time_corrected = time.time()
                                result = raw_sql_tool.invoke({"query": corrected_sql})
                                elapsed_corrected = time.time() - start_time_corrected
                                
                                # Convert result to string
                                result_str = str(result).strip()
                                
                                logger.info(
                                    f"Corrected query executed successfully in {elapsed_corrected:.2f}s. "
                                    f"Results: {len(result_str)} characters"
                                )
                                
                                # If result is empty
                                if not result_str or result_str == "[]" or result_str == "":
                                    formatted_result = "No se encontraron datos que coincidan con la consulta."
                                    logger.info("Corrected query executed successfully but no results. Returning formatted message.")
                                    set_cached_result(corrected_sql, formatted_result)
                                    _SQL_EXECUTION_INFO.set((corrected_sql, False))
                                    return formatted_result
                                else:
                                    # Save to cache
                                    set_cached_result(corrected_sql, result)
                                
                                # Report successful correction for learning
                                report_successful_correction(
                                    original_sql=query,
                                    error_message=error_msg,
                                    corrected_sql=corrected_sql
                                )
                                
                                _SQL_EXECUTION_INFO.set((corrected_sql, False))
                                return result
                                
                            except Exception as validation_error:
                                logger.warning(
                                    f"Corrected query failed validation: {validation_error}. "
                                    f"Returning original error."
                                )
                        else:
                            logger.warning("Could not generate a valid corrected query")
                            
                    except Exception as recovery_error:
                        logger.warning(f"Error during automatic recovery: {recovery_error}")
                
                # If recovery failed, return original error
                final_error_msg = f"Error al ejecutar query en BD (después de {elapsed:.2f}s): {error_msg}"
                logger.error(final_error_msg)
                return final_error_msg

        except Exception as e:
            error_msg = f"Error al ejecutar query: {str(e)}"
            logger.error(f"{error_msg}. Query: {query[:100]}...")
            return error_msg

    return validated_sql_query