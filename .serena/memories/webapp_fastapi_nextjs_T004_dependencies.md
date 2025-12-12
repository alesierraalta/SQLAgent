# T-004 — Dependencias backend + comandos

## Cambios
- `requirements.txt`:
  - Agregado: `fastapi>=0.115.0`
  - Agregado: `uvicorn[standard]>=0.27.0`
  - Agregado: `httpx>=0.26.0` (para tests con `TestClient`)

## Entrypoint de ejecución
- Agregado `src/api/__main__.py` para habilitar: `python -m src.api`
  - Env vars: `WEB_API_HOST` (default `127.0.0.1`), `WEB_API_PORT` (default `8000`), `WEB_API_RELOAD` (default `false`).

## Documentación
- README actualizado con comandos de ejecución del API y healthcheck (`/api/v1/health`).

## Notas
- `orjson` queda pendiente (solo si se decide usar `ORJSONResponse`).