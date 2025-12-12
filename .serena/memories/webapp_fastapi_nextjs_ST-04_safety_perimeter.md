ST-04 — Safety perimeter (localhost + CORS)

- Backend bind por defecto a `127.0.0.1` (no exponer en red accidentalmente).
- CORS: `allow_origins` explícito (default `http://localhost:3000`), `allow_credentials=False`.
- Métodos permitidos: mínimo `GET` (schema/health/stream) y `POST` (query/validate).
- Nunca exponer secretos al cliente; el browser solo conoce `NEXT_PUBLIC_API_BASE_URL`.
- Cambios para “abrir a red” quedan fuera de MVP y deben requerir configuración explícita.
