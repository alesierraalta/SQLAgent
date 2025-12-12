# ST-02 — Contrato de API v1 (MVP)

- Prefijo: `/api/v1`.
- Health: `GET /health` → `{status}`.
- Query single-shot: `POST /query` → `QueryResponse` (incluye `rows/columns`, `sql_generated`, `execution_time`, `tokens_*`, `cache_hit_type`, `model_used`).
- Query streaming SSE: `GET /query/stream?question=...` → `text/event-stream` con eventos `sql|analysis|execution|error|done`.
- Schema: `GET /schema?compact=true&max_tables=&force_refresh=` → `SchemaResponse`.
- History: `GET /history?limit=&offset=&days=` y `POST /history/clear`.
- Stats: `GET /stats?days=&slow_threshold_seconds=&limit=` → JSON con agregados y listas.
- Validate SQL: `POST /validate-sql` → `{valid, errors, tables}`.
