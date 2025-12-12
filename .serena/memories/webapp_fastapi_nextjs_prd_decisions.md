# WebApp FastAPI + Next.js — Decision Log (PRD)

## Decisiones (siempre RECOMMENDED)

### 1) Stack web
- **Frontend**: Next.js (App Router) + Tailwind + **Magic UI**.
- **Backend**: FastAPI dentro del repo (reusa `src/agents/sql_agent.py`, `src/validators/*`, `src/utils/*`, `src/schemas/*`).

**Rationale**
- Permite UX moderna (Magic UI) sin reescribir el core en JS.
- Mantiene la seguridad/validación en Python (una sola fuente de verdad).
- Deja listo el camino para futuras fases (chat, auth, multiusuario) sin rehacer arquitectura.

### 2) Acceso / seguridad
- **Sin auth (MVP)**, pero **solo localhost**: bind por defecto a `127.0.0.1`.
- **CORS restringido** por defecto a `http://localhost:3000` (configurable por env var).

**Rationale**
- MVP local con mínima superficie de ataque.
- Evita exponer el API en red accidentalmente.

### 3) UX primaria
- **Formulario single-shot** (pregunta → resultados) + opcional **ver SQL** / **explain**.
- **Streaming**: opcional, pero el diseño debe contemplarlo (SSE recomendado).

**Rationale**
- Mapea directo a `execute_query(..., return_metadata=True)`.
- Menor complejidad que un chat multi-turn.

## Contrato de streaming (propuesta)
- Transporte: **SSE** (`text/event-stream`) con eventos:
  - `sql`, `analysis`, `execution`, `error`, `done`
- Fuente: `execute_query(..., stream=True, stream_callback=...)`.

## Links a consultar (índice inicial)

### Context7
- FastAPI: `/fastapi/fastapi` (CORS, StreamingResponse, testing)
- Next.js: `/vercel/next.js` (App Router, environment variables)

### Docfork (navegación)
- FastAPI custom responses / StreamingResponse / ORJSONResponse:
  - https://github.com/tiangolo/fastapi/blob/0.124.0/docs/en/docs/advanced/custom-response.md#L1-L282

### Magic UI MCP
- Catálogo de componentes: `mcp__magicuidesign__getUIComponents`

## TODO (para Task T-002)
- Expandir links SSE + consumo en browser/Next.js.
- Definir CORS exacto (origins/headers/methods) y defaults.
- Confirmar estrategia de serialización (JSON vs ORJSONResponse).
