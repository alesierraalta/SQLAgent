# Repository Guidelines

## Project Structure & Modules
- Core code lives in `src/`: `agents/` (LangChain orchestration), `validators/` (SQL guards), `schemas/` (static schema fallback), `utils/` (DB, logging, history), and `cli.py` as the entry point.
- Tests in `tests/` mirror modules (`tests/test_sql_validator.py`, etc.). Utility scripts live in `scripts/` (e.g., `generate_test_data.py`).
- Environment examples sit in `.env.example`; do not commit `.env`.

## Setup, Build & Run
- Install deps: `pip install -r requirements.txt` (use the repo’s `.venv`).
- Seed sample data (optional): `python scripts/generate_test_data.py` after setting `DATABASE_URL`.
- Run natural-language queries: `python -m src.cli query "Top 10 productos por ventas" --limit 10 --verbose`.
- Inspect schema: `python -m src.cli schema`. Validate SQL manually: `python -m src.cli validate-sql "SELECT * FROM sales"`.
- Connectivity check: `python -m src.cli test-connection`.

## Coding Style & Naming
- Python 3.8+, 4-space indentation, type hints everywhere; keep functions small and side-effect aware.
- Docstrings follow Google/NumPy style; prefer clear names: modules/functions/methods in `snake_case`, classes in `PascalCase`, constants in `UPPER_SNAKE`.
- Keep logging via existing helpers in `src/utils/logger.py`; avoid print.
- When adding schema, update `src/schemas/database_schema.py` and keep descriptions concise.

## Testing Guidelines
- Primary runner: `pytest` (default options enforce `-v`, strict markers, and coverage).
- Coverage gates: 80% minimum across `src/validators` and `src/utils/database.py` (`--cov-fail-under=80`). HTML report lands in `htmlcov/`.
- Mark long runs with `@pytest.mark.slow`; integration DB checks with `@pytest.mark.integration`. To skip them locally: `pytest -m "not slow and not integration"`.
- Name tests as `test_*.py`, functions `test_*`, classes `Test*`; mirror module under test.

## Commit & PR Expectations
- Use focused branches and imperative commit messages (e.g., `Add SQL fallback validation`); group related changes only.
- Include a brief PR description: problem, approach, tests run (`pytest ...`), and any schema changes or new env vars.
- If a change affects queries or safety checks, note validation steps and sample CLI commands used.

## Security & Configuration
- Never commit secrets; copy `.env.example` to `.env` and set `OPENAI_API_KEY`, `DATABASE_URL`, and model/env tuning flags (`OPENAI_MODEL`, `QUERY_TIMEOUT`, `CACHE_TTL_SECONDS`, `SCHEMA_DISCOVERY`, etc.).
- Prefer read-only DB roles; validators block mutating SQL—keep tests against disposable data.
- For performance toggles (`USE_FAST_MODEL`, `ENABLE_SEMANTIC_CACHE`), document defaults when altering behavior.
