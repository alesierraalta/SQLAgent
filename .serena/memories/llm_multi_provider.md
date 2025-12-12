Se agregó soporte multi-proveedor de LLM vía LangChain.

Cambios clave:
- Nuevo módulo: src/utils/llm_factory.py
  - Selección por env: LLM_PROVIDER (openai|anthropic|google/gemini), LLM_MODEL, OPENAI_MODEL (legacy).
  - Helpers: normalize_provider(), get_default_model_name(), get_chat_model(require_tools=...), bind_tools_safe().
  - Imports lazy por proveedor: langchain_openai / langchain_anthropic / langchain_google_genai.
  - En flujo SQL (require_tools=True) se valida tool calling.

Refactors:
- src/agents/sql_agent.py: create_sql_agent usa get_chat_model(...) y bind_tools_safe(...) en lugar de ChatOpenAI directo.
- src/agents/error_recovery.py y src/agents/query_explainer.py: usan get_chat_model(...) en lugar de ChatOpenAI.

Config:
- .env.example: se añadieron LLM_PROVIDER, LLM_MODEL, LLM_API_KEY y keys por proveedor (ANTHROPIC_API_KEY, GOOGLE_API_KEY) + FAST_MODEL/COMPLEX_MODEL.
- requirements.txt: se agregaron dependencias langchain-anthropic y langchain-google-genai.

Tests:
- Se actualizaron patches de ChatOpenAI a get_chat_model.
- Nuevo: tests/test_llm_factory.py.

Ejecución tests:
- OK: .\.venv\Scripts\python -m pytest -m "not slow and not integration"