# T-003 — Estructura backend `src/api/`

## Resultado
Se creó el esqueleto del backend FastAPI con versionado `/api/v1` y routers por dominio.

## Archivos creados
- `src/api/app.py`: `create_app()` + `app`, incluye routers bajo `/api/v1`.
- `src/api/models.py`: `HealthResponse` (Pydantic).
- `src/api/routers/health.py`: `GET /health` (sale como `/api/v1/health`).
- `src/api/routers/query.py|schema.py|history.py|stats.py`: placeholders con `APIRouter(tags=[...])`.
- `src/api/services/query_service.py`: placeholder (NotImplemented).

## Nota
- No se agregó aún CORS/config/depencias (queda para T-004/T-005).
