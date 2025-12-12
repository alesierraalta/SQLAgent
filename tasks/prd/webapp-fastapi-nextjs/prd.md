# PRD — WebApp de Consultas (FastAPI + Next.js + Magic UI)

## Resumen
Agregar un frontend web (además del CLI existente) para ejecutar consultas en lenguaje natural contra el Data Warehouse, reutilizando el core actual (schema discovery/whitelist, SQL agent, validación, cache y métricas) y manteniendo el modo **seguro** (solo `SELECT`).

El MVP se orienta a uso local (sin autenticación), con backend Python (FastAPI) y frontend Next.js con Tailwind + Magic UI.

## Artefactos
- PRD: `tasks/prd/webapp-fastapi-nextjs/prd.md`
- Tasks (backlog + checklists): `tasks/prd/webapp-fastapi-nextjs/tasks/tasks.md`

## Contexto actual (baseline)
- El proyecto hoy es Python y ya soporta: `query`, `schema`, `validate-sql`, `history`, `stats`, `test-connection`.
- El flujo core reutilizable vive en:
  - `src/agents/sql_agent.py`: `create_sql_agent(...)`, `execute_query(..., return_metadata, stream, stream_callback)`.
  - `src/schemas/database_schema.py`: `load_schema(...)` (discovery + fallback + cache TTL).
  - `src/validators/sql_validator.py`: bloquea mutaciones y valida tablas/columnas permitidas.
  - `src/utils/database.py`: engine/pooling/timeouts/read-only.

## Objetivos
1. Proveer UI web moderna para correr queries NL y ver resultados.
2. Reutilizar el core existente (no duplicar lógica de seguridad/SQL/DB).
3. Mantener seguridad por defecto: **solo local**, CORS restringido, sin credenciales en el browser.
4. Soportar:
   - Ver respuesta (tabla/JSON) y exportación.
   - Ver SQL generado y (opcional) explicación del plan/SQL.
   - Streaming (opcional en MVP, pero con diseño listo para activarlo).

## No-objetivos (MVP)
- Auth/SSO/RBAC multiusuario.
- Escritura en BD (INSERT/UPDATE/DELETE/DROP) o “admin UI”.
- Persistir conversaciones tipo chat multi-turn (el CLI ya tiene modo chat; la web lo deja para fase posterior).

## Usuarios objetivo
- Analista/BI: quiere ejecutar preguntas rápidas sin terminal.
- Dev/DS: quiere ver SQL, tiempos, tokens, cache hits y exportar resultados.

## Métricas de éxito (MVP)
- Time-to-first-query < 2 min (setup + correr primera consulta).
- 95% de queries con respuesta sin error (excluye errores de BD/config).
- Latencia percibida: streaming o loading states claros.
- “Zero foot-guns”: no exponer el API fuera de `localhost` por defecto.

## Decisiones (selección automática: siempre RECOMMENDED)

How should we build the new query frontend (given the repo today is Python-only: Click/Rich CLI + `src/agents/sql_agent.py` for `create_sql_agent/execute_query`, and no web framework installed)?
a) Next.js (React) + Tailwind + Magic UI, consuming a FastAPI backend in this repo. (RECOMMENDED: UX moderna + Magic UI) ✅ ELEGIDA
pros:
- UI moderna con componentes de Magic UI, mejor experiencia que HTML-first.
- Separación clara: backend Python mantiene seguridad/DB; frontend solo consume.
- Escala mejor a features futuras (chat, auth, multiusuario).
contras:
- Requiere toolchain Node + build.
- Requiere contrato API y CORS.
b) FastAPI + Jinja2 + HTMX + Tailwind (server-rendered, “HTML-first”).
pros:
- Menos moving parts (solo Python).
contras:
- Magic UI (React) no aplica directamente; UX moderna cuesta más.
c) Streamlit (o Gradio) como app Python-only.
pros:
- MVP ultra rápido.
contras:
- Menos control, más difícil de harden en producción; Magic UI no aplica.

How should the web app handle authentication/access?
a) Sin auth, solo `localhost` (bind 127.0.0.1). (RECOMMENDED: MVP local seguro) ✅ ELEGIDA
pros:
- Menor fricción, mínimo alcance.
- Superficie de ataque baja si no se expone.
contras:
- No apto para deploy remoto sin cambios.
b) Password simple (Basic Auth) + env var.
pros:
- Barrera mínima.
contras:
- Seguridad limitada, gestión manual.
c) SSO/OAuth (Google/Microsoft/Okta).
pros:
- Mejor para multiusuario.
contras:
- Mucho mayor alcance.

How should the primary UX for running queries look?
a) Form “single-shot” (pregunta → resultados) + opcional “ver SQL” / “explain”. (RECOMMENDED: entrega más rápida) ✅ ELEGIDA
pros:
- Mapea 1:1 a `execute_query(..., return_metadata=True)`.
- Menos complejidad que chat.
contras:
- Menos iterativo que un chat.
b) Chat UI con streaming.
pros:
- Exploración más natural.
contras:
- Estado/sesiones complejos.
c) Ambas (tabs).
pros:
- Cubre todo.
contras:
- Aumenta alcance.

## Alcance funcional (MVP)

### Backend (FastAPI)
Endpoints v1 propuestos (prefijo `/api/v1`):
- `GET /health`: estado del servicio (sin tocar DB).
- `GET /test-connection`: verifica conexión a DB (reusa `src/utils/database.py`).
- `GET /schema`: devuelve schema (compacto y/o completo) desde `load_schema`.
- `POST /query`:
  - input: `{ question, limit?, format?, explain?, stream? }`
  - output: `{ response, sql_generated?, execution_time?, tokens_*, cache_hit_type?, model_used?, error? }`
- `GET /history`: historial (reusa `src/utils/history.py`).
- `POST /validate-sql`: valida SQL manual (reusa `SQLValidator`).
- `GET /stats`: expone métricas (si hoy están “pegadas” al CLI, extraer a `src/utils/stats.py`).

Streaming (MVP opcional; diseño obligatorio):
- `GET /query/stream` (SSE `text/event-stream`) o `POST /query/stream` si se requiere body:
  - Emite eventos: `sql`, `execution`, `analysis`, `error`, `done`.
  - Fuente: `execute_query(..., stream=True, stream_callback=...)`.

### Frontend (Next.js + Tailwind + Magic UI)
Páginas:
- `/` Query:
  - Textarea “Pregunta”.
  - “Advanced options” (limit/format/explain/stream).
  - Resultado: tabla + panel “SQL generado” con botón copy.
  - Estado loading + errores.
- `/schema`:
  - Viewer de tablas/columnas + búsqueda.
- `/history`:
  - Lista de últimas queries (timestamp, pregunta, cache hit, modelo).
- `/stats`:
  - Métricas (tiempo promedio, cache hit rate, tokens promedio).

Componentes recomendados (Magic UI):
- Botón ejecutar: `shimmer-button` o `shiny-button`.
- Panel de streaming/log: `terminal`.
- “Copy SQL”: usar componente estilo `script-copy-btn` (si se adopta) o un botón propio.
- Layout/hero (opcional): `bento-grid`, `animated-gradient-text`, `animated-theme-toggler`.

## Requisitos no funcionales
- Seguridad:
  - Backend bind a `127.0.0.1` por defecto.
  - CORS explícito solo a `http://localhost:3000` en dev (y lista configurable).
  - Nunca exponer `DATABASE_URL` ni secretos al cliente.
  - Mantener validación estricta SQL (solo SELECT).
- Rendimiento:
  - Reusar pooling existente.
  - Preferir respuesta JSON ya serializable (evaluar `ORJSONResponse`).
  - Mantener/mostrar señales de cache hit (SQL/semantic).
- Observabilidad:
  - Logging con `src/utils/logger.py`.
  - Preparar hooks para OpenTelemetry si ya está en requirements (fase posterior).
- UX:
  - Accesible (teclado), feedback claro, persistencia de última configuración (localStorage).

## Configuración / Variables de entorno (propuesta)
Backend:
- `WEB_API_HOST` (default `127.0.0.1`)
- `WEB_API_PORT` (default `8000`)
- `WEB_ALLOWED_ORIGINS` (CSV, default `http://localhost:3000`)

Frontend:
- `NEXT_PUBLIC_API_BASE_URL` (default `http://127.0.0.1:8000/api/v1`)

## Arquitectura propuesta (dentro del repo)
Backend:
- Nuevo paquete `src/api/`:
  - `src/api/app.py` (crea FastAPI, middleware, routers)
  - `src/api/models.py` (Pydantic request/response del API)
  - `src/api/routers/query.py`, `schema.py`, `history.py`, `stats.py`, `health.py`
  - `src/api/services/query_service.py` (orquesta `load_schema + get_db_engine + create_sql_agent + execute_query`)

Frontend:
- Nuevo directorio `frontend/` (Next.js App Router).

## Riesgos y mitigaciones
- Duplicación de lógica entre CLI y API:
  - Mitigar extrayendo servicios utilitarios (p.ej. stats) a `src/utils/*` y reusar.
- Streaming:
  - SSE es más simple que WebSocket para “push” incremental; se apoya en `StreamingResponse`.
  - Mantener fallback a “single-shot” si el entorno/proxy corta SSE.
- Exposición accidental:
  - `host=127.0.0.1` por defecto + documentación explícita para abrir a red bajo flags.

## Proceso de trabajo (OBLIGATORIO: MCP-first)
Regla general: “primero herramientas MCP, después cambios”.
- Investigación local (OBLIGATORIO): Serena MCP (`list_dir`, `find_file`, `search_for_pattern`, `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`) antes de leer archivos completos.
- Después de una exploración: `mcp__serena__think_about_collected_information`.
- Antes de editar: `mcp__serena__think_about_task_adherence`.
- Docs/Best practices (OBLIGATORIO):
  - Context7 (`resolve-library-id`, `get-library-docs`) para APIs de FastAPI/Next.js.
  - Docfork (`docfork_search_docs`, `docfork_read_url`) como “navegador” para optimizaciones/patrones.
- UI (OBLIGATORIO): Magic UI MCP para seleccionar componentes y guiar implementación visual.
- Memoria (OBLIGATORIO): registrar decisiones/URLs/hallazgos en “bank memory” usando Serena `write_memory`.
