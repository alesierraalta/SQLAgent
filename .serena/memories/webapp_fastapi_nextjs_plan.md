Decisiones (RECOMMENDED):
- Frontend: Next.js (App Router) + Tailwind + Magic UI.
- Backend: FastAPI dentro del repo, reutilizando `src/agents/sql_agent.py` y validadores.
- Acceso: sin auth, solo localhost (bind 127.0.0.1) + CORS restringido.
- UX principal: formulario single-shot + ver SQL/explain; streaming SSE opcional.

Docs consultadas (para mejores prácticas):
- FastAPI StreamingResponse: Context7 `/fastapi/fastapi` topic `StreamingResponse`.
- FastAPI CORS (CORSMiddleware): Context7 `/fastapi/fastapi` topic `CORS`.
- Next.js App Router: Context7 `/vercel/next.js` topic `App Router`.
- Next.js env vars: Context7 `/vercel/next.js` topic `Environment Variables`.
- FastAPI custom responses/StreamingResponse y ORJSONResponse: Docfork https://github.com/tiangolo/fastapi/blob/0.124.0/docs/en/docs/advanced/custom-response.md#L1-L282
- Magic UI component catalog: `mcp__magicuidesign__getUIComponents`.

Entregables de planificación:
- PRD: `tasks/prd/webapp-fastapi-nextjs/prd.md`
- Backlog/checklists: `tasks/prd/webapp-fastapi-nextjs/tasks/tasks.md`

Notas:
- Para streaming se propone SSE (`text/event-stream`) con eventos `sql|execution|analysis|error|done`, adaptando `execute_query(..., stream_callback)`.
- Antes de cada cambio, usar Serena MCP para ubicar símbolos y minimizar lectura; persistir hallazgos y decisiones en memories.