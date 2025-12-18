"""
DEPRECATED: Use src.agents.builder and src.agents.executor instead.
This module acts as a facade for backward compatibility and testing.
"""

# Public API
from src.agents.builder import create_sql_agent
from src.agents.executor import execute_query

# Internal functions/classes re-exported for tests/backward compatibility
from src.agents.prompts import (
    generate_system_prompt as _generate_system_prompt,
    _select_candidate_tables,
    _render_schema_subset,
    classify_query_complexity as _classify_query_complexity
)
from src.agents.parser import parse_streaming_chunk as _parse_streaming_chunk
from src.agents.tools import _SQL_EXECUTION_INFO

# Imports that were present in the old file and are mocked/used by tests
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain.tools import tool as tool_decorator
from langchain.agents import create_agent
from src.utils.semantic_cache import get_semantic_cached_result, set_semantic_cached_result
from src.utils.llm_factory import get_chat_model, bind_tools_safe
from src.utils.ml_classifier import classify_query_complexity_ml
from src.validators.sql_validator import SQLValidator
from src.utils.few_shot_examples import get_relevant_examples, format_examples_for_prompt

__all__ = [
    "create_sql_agent", 
    "execute_query",
    "_generate_system_prompt",
    "_select_candidate_tables",
    "_render_schema_subset",
    "_classify_query_complexity",
    "_parse_streaming_chunk",
    "_SQL_EXECUTION_INFO",
    "SQLDatabaseToolkit",
    "SQLDatabase",
    "tool_decorator",
    "create_agent",
    "get_semantic_cached_result",
    "set_semantic_cached_result",
    "get_chat_model",
    "bind_tools_safe",
    "classify_query_complexity_ml",
    "SQLValidator",
    "get_relevant_examples",
    "format_examples_for_prompt"
]