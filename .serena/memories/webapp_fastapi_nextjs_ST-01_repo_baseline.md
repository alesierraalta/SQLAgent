# ST-01 — Baseline del repo (core reutilizable)

- CLI existente (`python -m src.cli ...`) ya soporta: `query`, `schema`, `validate-sql`, `history`, `stats`, `test-connection`.
- Core de queries NL→SQL vive en `src/agents/sql_agent.py`: `create_sql_agent(...)` + `execute_query(..., return_metadata, stream, stream_callback)`.
- Seguridad/guardrails SQL vive en `src/validators/sql_validator.py` (usa `src.utils.exceptions.*`).
- Schema vive en `src/schemas/database_schema.py`: `load_schema(use_discovery, force_refresh)` con cache TTL y fallback estático.
- Persistencia local: historial en `src/utils/history.py` (JSON file) y métricas en `src/utils/performance.py`.
- Logging centralizado: `src/utils/logger.py` (no usar `print`).
