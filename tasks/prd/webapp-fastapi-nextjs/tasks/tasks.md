# Tasks — WebApp de Consultas (FastAPI + Next.js + Magic UI)

## Reglas (OBLIGATORIAS) — “MCP-first / Token-minimal”
Estas reglas aplican a TODO el trabajo de este PRD.

### 1) Investigación local (Serena MCP) antes de leer/escribir
- [ ] Usar `mcp__serena__list_dir` / `mcp__serena__find_file` para ubicar archivos.
- [ ] Usar `mcp__serena__search_for_pattern` para encontrar puntos de integración.
- [ ] Usar `mcp__serena__get_symbols_overview` para entender módulos sin leer todo el archivo.
- [ ] Usar `mcp__serena__find_symbol(include_body=True)` solo para funciones/clases necesarias.
- [ ] Tras cada ronda de búsqueda: `mcp__serena__think_about_collected_information`.

### 2) Antes de cada cambio (edición)
- [ ] Ejecutar `mcp__serena__think_about_task_adherence` antes de modificar código.
- [ ] Editar con `apply_patch` (o `mcp__serena__replace_*` cuando aplique por símbolo/regex).

### 3) Docs + “navegador” (Context7 + Docfork)
- [ ] Para cada decisión técnica importante, consultar:
  - [ ] Context7: `mcp__context7__resolve-library-id` + `mcp__context7__get-library-docs`
  - [ ] Docfork: `mcp__docfork__docfork_search_docs` + `mcp__docfork__docfork_read_url`
- [ ] Guardar links y conclusiones en memoria (ver “Bank memory”).

### 4) UI (Magic UI)
- [ ] Seleccionar componentes desde `mcp__magicuidesign__getUIComponents`.
- [ ] Para componentes elegidos, consultar implementaciones con:
  - [ ] `mcp__magicuidesign__getComponents`
  - [ ] `mcp__magicuidesign__getButtons`
  - [ ] `mcp__magicuidesign__getTextAnimations`
  - [ ] `mcp__magicuidesign__getBackgrounds`

### 5) Bank memory (Serena memories)
- [ ] Usar `mcp__serena__write_memory` para:
  - [ ] decisiones (stack, endpoints, CORS, streaming)
  - [ ] URLs de docs relevantes
  - [ ] riesgos y mitigaciones
  - [ ] checklists completadas/pendientes

### 6) Paralelización (cuando aplique)
- [ ] Usar `multi_tool_use.parallel` para búsquedas/lecturas independientes.

## Sequential Thinking (ST) — 20 checkpoints mínimos (OBLIGATORIOS)
En cada checkpoint, producir un mini‑resultado verificable (3–7 bullets) y persistirlo en memoria.
- [x] ST-01: Confirmar baseline del repo (CLI, módulos core, rutas candidatas).
- [x] ST-02: Definir contrato de API v1 (endpoints + modelos + errores).
- [x] ST-03: Decidir estrategia de streaming (SSE vs fetch streaming) y fallback.
- [x] ST-04: Diseñar “safety perimeter” (localhost bind + CORS + límites).
- [ ] ST-05: Plan de reutilización (qué se extrae del CLI a services/utils).
- [x] ST-06: Diseño de modelos Pydantic del API (requests/responses).
- [ ] ST-07: Estrategia de serialización/performance (JSON vs ORJSONResponse).
- [ ] ST-08: Estrategia de manejo de errores (tipos, status codes, mensajes).
- [ ] ST-09: Estrategia de timeouts/cancelación para queries largas.
- [ ] ST-10: Estrategia de cache (semantic/sql) + métricas y “cache_hit_type”.
- [x] ST-11: Contrato de streaming events (sql/execution/analysis/error/done).
- [ ] ST-12: UI wireframe de Query page (layout + estados + accesibilidad).
- [ ] ST-13: UI wireframe de Schema/History/Stats (info mínima viable).
- [ ] ST-14: Selección final de Magic UI components (y por qué).
- [ ] ST-15: Estrategia de export (CSV/JSON/Excel) y límites.
- [ ] ST-16: Plan de tests backend (unit + integration markers).
- [ ] ST-17: Plan de tests frontend (smoke + contratos).
- [ ] ST-18: Plan de DX local (comandos, scripts, .env.example).
- [ ] ST-19: Plan de seguridad para “abrir a red” (NO MVP; cómo habilitar seguro).
- [ ] ST-20: Checklist final de aceptación (DoD y demo script).

---

## Backlog (ultra-específico) — WebApp FastAPI + Next.js

### T-001 — Crear “decision log” + memoria del PRD
Checklist:
- [x] `mcp__serena__write_memory`: guardar decisiones RECOMMENDED del PRD + rationale.
- [x] `mcp__serena__write_memory`: guardar un índice de links (Context7/Docfork) a consultar.
DoD:
- [x] Existe memoria `webapp_fastapi_nextjs_prd_decisions.md` con decisiones y links placeholder.

### T-002 — Investigación de mejores prácticas (FastAPI + Next.js + SSE) (Docs-first)
Checklist:
- [x] Context7:
  - [x] Resolver IDs para FastAPI y Next.js.
  - [x] Leer docs sobre `CORSMiddleware`, `StreamingResponse`, tests.
  - [x] Leer docs App Router + env vars (`NEXT_PUBLIC_*`).
- [x] Docfork (“navegador”):
  - [x] Buscar patrones de SSE en FastAPI/Starlette.
  - [x] Buscar patrones de consumo SSE en browser/Next.js.
  - [x] Buscar recomendaciones de CORS para localhost.
- [x] `mcp__serena__write_memory`: guardar conclusiones y decisión final de SSE.
DoD:
- [x] Memoria con 5–10 links y “key takeaways” accionables.

### T-003 — Definir estructura del backend `src/api/` (sin implementar lógica aún)
Checklist:
- [x] `mcp__serena__list_dir` + `mcp__serena__find_file`: confirmar estructura actual de `src/`.
- [x] Crear carpetas/archivos propuestos:
  - [x] `src/api/__init__.py`
  - [x] `src/api/app.py`
  - [x] `src/api/models.py`
  - [x] `src/api/routers/` + routers base (`health.py`, `query.py`, `schema.py`, `history.py`, `stats.py`)
  - [x] `src/api/services/query_service.py`
- [x] Definir `FastAPI()` con versionado `/api/v1` y tags por router.
DoD:
- [x] App levanta y sirve `GET /api/v1/health` (mock).

### T-004 — Agregar dependencias backend (FastAPI + Uvicorn + test client) y comandos
Checklist:
- [x] `mcp__serena__read_file` (chunk) de `requirements.txt` para confirmar baseline.
- [ ] Definir dependencias mínimas:
  - [x] `fastapi`
  - [x] `uvicorn[standard]`
  - [x] `httpx` (para tests de TestClient si se requiere)
  - [ ] (Opcional) `orjson` si se decide `ORJSONResponse`
- [ ] Actualizar `requirements.txt` y documentación de ejecución:
  - [x] comando dev: `python -m src.api` o `uvicorn src.api.app:app --host 127.0.0.1 --port 8000`
- [x] `mcp__serena__write_memory`: registrar nuevas deps y versiones sugeridas.
DoD:
- [x] Requirements actualizados y documentados.

### T-005 — Implementar configuración segura (localhost bind + CORS restringido)
Checklist:
- [x] Context7: revisar parámetros de `CORSMiddleware` (`allow_origins`, `allow_methods`, `allow_headers`).
- [x] Implementar `WEB_API_HOST`, `WEB_API_PORT`, `WEB_ALLOWED_ORIGINS`:
  - [x] default host `127.0.0.1`
  - [x] origins default `http://localhost:3000`
- [x] `mcp__serena__write_memory`: registrar “safety perimeter” y cómo cambiarlo.
DoD:
- [x] CORS solo permite origins explícitas.

### T-006 — Endpoint `POST /api/v1/query` (single-shot)
Checklist (reusar core):
- [x] `mcp__serena__get_symbols_overview` de `src/agents/sql_agent.py`, `src/schemas/database_schema.py`, `src/utils/database.py`.
- [x] `mcp__serena__find_symbol(include_body=True)` de `load_schema`, `get_db_engine`, `create_sql_agent`, `execute_query` (solo lo necesario).
- [ ] Implementar request model:
  - [x] `question: str`
  - [x] `limit: int | None`
  - [x] `format: "table" | "json"` (para UI; backend devuelve JSON estructurado)
  - [x] `explain: bool`
  - [x] `stream: bool` (rechazar/ignorar en endpoint single-shot)
- [ ] Implementar response model:
  - [x] `response_text: str` (si el core retorna texto)
  - [x] `rows: list[dict] | None` (si se logra estructurar)
  - [x] `sql_generated: str | None`
  - [x] `execution_time: float | None`
  - [x] `tokens_*`, `cache_hit_type`, `model_used`
  - [x] `error: {code,message} | None`
- [x] Guardar a history (si no está deshabilitado).
DoD:
- [x] Endpoint funciona para una query simple y retorna metadata.

### T-007 — Endpoint de streaming `GET/POST /api/v1/query/stream` (SSE)
Checklist:
- [x] ST-03/ST-11: confirmar contrato de eventos SSE.
- [x] Implementar SSE con `StreamingResponse(media_type="text/event-stream")`.
- [x] Adaptar `execute_query(..., stream=True, stream_callback=...)`:
  - [x] callback encola eventos (`sql`, `execution`, `analysis`, `error`).
  - [x] enviar `done` al final con resumen (sql final, elapsed, cache hit).
- [x] Manejo de cancelación:
  - [x] desconexión del cliente detiene generator.
DoD:
- [x] UI (mínima) puede consumir SSE y renderizar chunks.

### T-008 — Endpoint `GET /api/v1/schema`
Checklist:
- [x] Reusar `load_schema(force_refresh?)`.
- [x] Agregar query params:
  - [x] `compact=true|false`
  - [x] `max_tables` (si aplica al subset)
- [x] Devolver formato consistente (tables, columns, pk/fk, descriptions).
DoD:
- [x] Schema visible desde web sin exponer credenciales.

### T-009 — Endpoint `POST /api/v1/validate-sql`
Checklist:
- [x] Reusar `SQLValidator`.
- [x] Responder con:
  - [x] `valid: bool`
  - [x] `errors: list[str]`
  - [x] `tables: list[str]` (si está disponible)
DoD:
- [x] Bloquea mutaciones y tablas/columnas no permitidas.

### T-010 — Endpoints `GET /api/v1/history` y `POST /api/v1/history/clear`
Checklist:
- [x] Reusar `src/utils/history.py`.
- [x] Implementar paginación básica (`limit`, `offset`) y filtros (`days`).
DoD:
- [x] UI puede listar historial y borrarlo.

### T-011 — Endpoint `GET /api/v1/stats`
Checklist:
- [x] Localizar dónde vive la lógica de stats hoy (probablemente en `src/cli.py`).
- [x] Extraer a `src/utils/stats.py` (si aplica) y reusar en CLI + API. (ya existe en `src/utils/performance.py`)
- [x] Devolver un JSON de métricas (no texto “Rich”).
DoD:
- [x] `GET /stats` devuelve JSON estable.

### T-012 — Tests backend (pytest)
Checklist:
- [x] Crear `tests/test_api_*.py` con `TestClient` (FastAPI).
- [ ] Tests mínimos:
  - [x] `GET /health` 200
  - [x] `POST /query` valida input y retorna estructura
  - [x] `POST /validate-sql` bloquea `DROP`
  - [x] `GET /schema` retorna tablas
- [ ] Marcar integración DB real con `@pytest.mark.integration`.
DoD:
- [x] `pytest -m "not integration and not slow"` pasa.

---

## Frontend (Next.js + Tailwind + Magic UI)

### T-020 — Scaffold Next.js en `frontend/` (App Router + TypeScript)
Checklist:
- [x] Decidir carpeta: `frontend/` (RECOMMENDED).
- [ ] `mcp__context7__get-library-docs`: App Router + env vars.
- [ ] Crear app:
  - [x] App Router (`app/`)
  - [x] Tailwind config
  - [x] ESLint básico
- [x] Definir `NEXT_PUBLIC_API_BASE_URL`.
DoD:
- [ ] `npm run dev` levanta UI base.

### T-021 — Sistema de diseño (Tailwind + Magic UI baseline)
Checklist:
- [ ] `mcp__magicuidesign__getUIComponents`: elegir set mínimo:
  - [ ] `shimmer-button` o `shiny-button`
  - [ ] `terminal` (stream)
  - [ ] `animated-theme-toggler` (opcional)
- [ ] Implementar layout base:
  - [x] Navbar (Query/Schema/History/Stats)
  - [x] Dark mode (opcional)
DoD:
- [ ] UI consistente en 4 rutas.

### T-022 — Página `/` Query (single-shot)
Checklist:
- [x] Form:
  - [x] Textarea pregunta
  - [x] botón ejecutar (Magic UI)
  - [x] Advanced options (limit/explain)
- [x] Llamada API:
  - [x] POST `/api/v1/query`
  - [x] manejar loading/error
- [x] Resultado:
  - [x] Tabla render (simple)
  - [x] Panel SQL + copy
DoD:
- [x] Ejecuta una query y muestra resultados.

### T-023 — Soporte streaming (SSE) en Query page (opt-in)
Checklist:
- [x] Toggle “Streaming”.
- [x] Consumir SSE (`EventSource`) y renderizar eventos:
  - [x] `sql` -> panel SQL
  - [x] `analysis` -> terminal/log
  - [x] `execution` -> resultado final
- [x] Fallback a single-shot si falla.
DoD:
- [x] Streaming funciona en dev.

### T-024 — Página `/schema`
Checklist:
- [x] GET `/api/v1/schema`
- [x] Viewer:
  - [x] búsqueda por tabla/columna
  - [ ] collapsible por tabla
DoD:
- [x] Usuario encuentra columnas rápidamente.

### T-025 — Página `/history`
Checklist:
- [x] GET `/api/v1/history`
- [x] UI:
  - [x] lista con timestamp/pregunta/cache/modelo
  - [x] botón clear history (confirm)
DoD:
- [x] Historial navegable.

### T-026 — Página `/stats`
Checklist:
- [x] GET `/api/v1/stats`
- [x] UI mínima:
  - [x] cards métricas
  - [x] tablas top slow queries si aplica
DoD:
- [x] Stats visibles y entendibles.

---

## Documentación y DX

### T-030 — README + comandos de ejecución local
Checklist:
- [x] Documentar:
  - [x] correr backend (FastAPI)
  - [x] correr frontend (Next)
  - [x] variables env (backend + frontend)
- [ ] Incluir “demo script” (pasos para probar).
DoD:
- [ ] Onboarding en 5–10 minutos.

### T-031 — .env.example actualizado (sin secretos)
Checklist:
- [x] Agregar variables nuevas con defaults seguros.
DoD:
- [x] `.env.example` completo y consistente.

---

## Cierre

### T-999 — Validación final (DoD)
Checklist:
- [ ] ST-20 completado y guardado en memoria.
- [ ] Backend: endpoints principales funcionan.
- [ ] Frontend: Query/Schema/History/Stats funcionales.
- [ ] Seguridad: bind localhost + CORS restringido + sin secretos en cliente.
- [ ] Tests: suite no-integration pasa.
