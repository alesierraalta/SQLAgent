# ST-11 — Contrato de eventos SSE (query streaming)

- Endpoint: `GET /api/v1/query/stream` (EventSource-friendly).
- Parámetros: `question` (max 2000 chars), `limit` (opcional), `explain` (bool).
- Formato: frames SSE con `event: <tipo>` y `data: <json>`.
- Tipos soportados:
  - `sql`: `{type:'sql', content, sql, complete}`
  - `analysis`: `{type:'analysis', content, complete}`
  - `execution`: `{type:'execution', content, complete}`
  - `error`: `{code,message}` o `{type:'error', content}` (cliente debe tolerar ambos)
  - `done`: `QueryResponse` completo (resultado final)
- Cancelación: si el cliente se desconecta, el generator se detiene y se ignoran callbacks subsecuentes (best-effort).
