# T-002 — Docs-first findings (FastAPI + Next.js + SSE)

## Links consultados (navegación)
- FastAPI CORS (CORSMiddleware): https://github.com/tiangolo/fastapi/blob/0.124.0/docs/en/docs/tutorial/cors.md#L1-L88
- FastAPI custom responses / StreamingResponse: https://github.com/tiangolo/fastapi/blob/0.124.0/docs/en/docs/advanced/custom-response.md#L1-L282
- Starlette StreamingResponse: https://github.com/Kludex/starlette/blob/main/docs/responses.md#L127-L149
- FastAPI testing: https://github.com/fastapi/fastapi/blob/master/docs/en/docs/tutorial/testing.md
- FastAPI async tests: https://github.com/fastapi/fastapi/blob/master/docs/en/docs/advanced/async-tests.md
- Next.js Route Handlers (App Router): https://github.com/vercel/next.js/blob/canary/docs/01-app/03-api-reference/03-file-conventions/route.mdx
- Next.js Route Handlers — streaming (AI SDK example): https://github.com/vercel/next.js/blob/canary/docs/01-app/03-api-reference/03-file-conventions/route.mdx#L349-L368
- Next.js Route Handlers — streaming (ReadableStream example): https://github.com/vercel/next.js/blob/canary/docs/01-app/03-api-reference/03-file-conventions/route.mdx#L427-L465
- Next.js Pages API — streaming SSE (`text/event-stream`): https://github.com/vercel/next.js/blob/canary/docs/02-pages/03-building-your-application/01-routing/07-api-routes.mdx#L441-L455
- Next.js env vars: https://github.com/vercel/next.js/blob/canary/docs/01-app/02-guides/environment-variables.mdx

## Key takeaways (accionables)
- CORS en FastAPI: preferir `allow_origins` explícito (localhost dev), `allow_credentials=False`; si no hay credenciales, no usar wildcard por defecto igualmente.
- `StreamingResponse` (FastAPI/Starlette) soporta generator/async generator para enviar cuerpo por partes; para SSE se usa `media_type='text/event-stream'`.
- SSE: enviar frames con formato tipo `data: ...\n\n` (y opcionalmente `event: nombre\n`), y deshabilitar cache (ej. `Cache-Control: no-store`).
- Next.js puede hacer streaming desde un handler devolviendo `Response(stream)` (ReadableStream). Útil si en el futuro se quiere proxy (misma origin) en vez de CORS.
- Testing FastAPI: usar `TestClient` (requiere `httpx`); si se usan eventos lifespan/startup/shutdown, preferir `with TestClient(app) as client:`.

## Decisión final SSE (para este repo)
- Transporte: **SSE**.
- Backend: FastAPI `StreamingResponse(media_type='text/event-stream')`.
- Formato de eventos: `event: sql|analysis|execution|error|done` + `data: <json>` + separación por línea en blanco.
- Cliente: `EventSource` en el browser.
- Endpoint recomendado: `GET /api/v1/query/stream` para compatibilidad con `EventSource`.
  - Mitigación URL-length: imponer límite (p.ej. 1500–2000 chars) y/o fallback a `POST /api/v1/query` (single-shot) cuando se exceda o si el usuario desactiva streaming.
- CORS: permitir explícitamente `http://localhost:3000` (configurable) y métodos `GET/POST`.
