ST-03 — Estrategia de streaming (SSE)

- Transporte elegido: SSE (`text/event-stream`) por simplicidad y compatibilidad en browser.
- Backend: FastAPI `StreamingResponse` con generator/async generator.
- Tipos de eventos: `sql`, `analysis`, `execution`, `error`, `done` (alineado a `execute_query(..., stream_callback)` existente).
- Cliente: `EventSource` (GET). Si el input excede límite de URL o el usuario desactiva streaming, fallback a `POST /query` single-shot.
- Headers recomendados: `Content-Type: text/event-stream`, `Cache-Control: no-store`.
