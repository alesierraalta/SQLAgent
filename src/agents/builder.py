"""Agent construction and configuration."""

import os
from typing import Any, Optional

from langchain.agents import create_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import Engine

from src.agents.prompts import generate_system_prompt
from src.agents.tools import create_validated_sql_tool
from src.schemas.database_schema import DatabaseSchema
from src.utils.llm_factory import bind_tools_safe, get_chat_model, get_default_model_name, normalize_provider
from src.utils.logger import logger
from src.utils.ml_classifier import classify_query_complexity_ml
from src.validators.sql_validator import SQLValidator


def create_sql_agent(
    engine: Engine,
    schema: DatabaseSchema,
    llm: Optional[BaseChatModel] = None,
    question: Optional[str] = None,
) -> Any:
    """
    Creates a LangChain agent for SQL queries with strict validation.

    Args:
        engine: SQLAlchemy Engine with database connection.
        schema: DatabaseSchema with allowed tables and columns.
        llm: LLM Model (optional, created from env vars).
        question: User question (optional, used for model selection and few-shot optimization).

    Returns:
        Configured LangChain agent.
    """
    # Initialize LLM if not provided
    if llm is None:
        # Model selection: allows configuring models by env
        provider = normalize_provider()
        default_model = get_default_model_name(provider)

        use_fast_model = os.getenv("USE_FAST_MODEL", "true").lower() in ("true", "1", "yes")
        fast_model = (os.getenv("FAST_MODEL") or "").strip() or default_model
        complex_model = (os.getenv("COMPLEX_MODEL") or "").strip() or default_model
        
        if use_fast_model and question:
            complexity = classify_query_complexity_ml(question)
            if complexity == "simple":
                model_name = fast_model
                logger.info(
                    f"Model Selection: Query classified as 'simple' "
                    f"(words: {len(question.split())}), using fast model: {model_name}"
                )
            else:
                model_name = complex_model
                logger.info(
                    f"Model Selection: Query classified as 'complex' "
                    f"(words: {len(question.split())}), using complex model: {model_name}"
                )
        else:
            model_name = default_model
            if question:
                logger.info(f"Model Selection: Using default model: {model_name} (USE_FAST_MODEL=false or missing question)")
            else:
                logger.info(f"Model Selection: Using default model: {model_name} (no question for classification)")
        
        # Configure prompt caching if enabled
        enable_prompt_caching = os.getenv("ENABLE_PROMPT_CACHING", "true").lower() in ("true", "1", "yes")
        if enable_prompt_caching and provider == "openai":
            logger.debug("Prompt caching enabled (requires prefix >1024 tokens)")
        
        llm = get_chat_model(
            model_name=model_name,
            provider=provider,
            temperature=0,
            max_tokens=None,
            require_tools=True,
        )

    # Create SQLDatabase wrapper
    db = SQLDatabase(engine)

    # Create toolkit
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    # Get tools from toolkit
    tools = toolkit.get_tools()

    # Create validator
    validator = SQLValidator(schema)

    # Find the sql_db_query tool from the toolkit
    sql_db_query_tool = None
    for t in tools:
        if t.name == "sql_db_query":
            sql_db_query_tool = t
            break

    if sql_db_query_tool is None:
        raise ValueError("Could not find 'sql_db_query' tool in toolkit")

    # Create custom validated tool
    validated_sql_query = create_validated_sql_tool(schema, validator, sql_db_query_tool)

    # Replace sql_db_query with our validated version
    validated_tools = []
    for tool in tools:
        if tool.name == "sql_db_query":
            validated_tools.append(validated_sql_query)
        else:
            validated_tools.append(tool)

    # Generate dynamic system prompt
    system_prompt = generate_system_prompt(schema, db.dialect, question=question)

    # Configure LLM with tool_choice to force execution
    # tool_choice="any" forces the model to use at least one tool when appropriate
    llm_with_tools = bind_tools_safe(llm, validated_tools, tool_choice="any")

    # Create agent
    agent = create_agent(
        llm_with_tools,
        validated_tools,
        system_prompt=system_prompt,
    )

    logger.info("SQL Agent created successfully")
    return agent