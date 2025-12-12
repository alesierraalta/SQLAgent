# ST-06 — Modelos Pydantic del API

- `src/api/models.py` define contratos estables para:
  - `QueryRequest/QueryResponse` (single-shot)
  - `SchemaResponse` (`SchemaTable/SchemaColumn`) con `response_model_exclude_none=True` para payload compacto
  - `ValidateSQLRequest/ValidateSQLResponse`
  - `HistoryEntry/HistoryResponse` + `ClearHistoryResponse`
- `QueryResponse.error` usa `APIError {code,message}` para errores uniformes sin excepciones HTTP.
