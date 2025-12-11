# Chat-First CLI (Fase 1: UX)

## Objetivo
CLI interactivo estilo chat (sin subcomandos) que use el agente SQL actual: prompt libre → valida/genera SQL → confirma (según modo) → ejecuta → muestra resultados. Seguridad y claridad primero.

## Flujo de sesión
- Inicio: `python -m src.cli_chat` abre bucle interactivo (Rich); muestra conexión activa, modelo y límites (`MAX_QUERY_ROWS`, `QUERY_TIMEOUT`).
- Interacción: prompt libre en español/inglés. Historial corto se pasa al agente.
- Confirmación:
  - Modo seguro (default): se muestra SQL validado y pide `/run` o `y/n`. Si el validador rechaza, se muestra motivo y sugerencia.
  - Modo directo: ejecuta tras validación, salvo bloqueos críticos.
- Resultado: tabla Rich paginada (o JSON plano con flag de arranque), tiempos (LLM, DB), filas truncadas con aviso y comando `/more`.
- Persistencia opcional: `/save path` guarda transcript + SQL + timings.

## Comandos de barra
- `/schema` imprime esquema resumido (usa schema compacto si existe).
- `/settings` muestra config activa; `/set key=value` cambia límites de sesión (p.ej. `limit`, `timeout`, `model`, `readonly`).
- `/retry` reenvía último prompt; `/history N` muestra N últimos turnos; `/clear` limpia pantalla/historial en memoria.
- `/sql` abre bloque para pegar SQL manual, validarlo y (opcional) ejecutarlo.
- `/export csv|json path` exporta último resultado.
- `/exit` o `Ctrl+C` para salir.

## Estados y modos
- Safe: requiere confirmación; bloquea mutaciones; límite de filas activo.
- Power: ejecuta tras validar; mantiene bloqueos a mutaciones y timeouts.
- Readonly DB sugerido; si no, forzar `DEFAULT_TRANSACTION_READ_ONLY`.

## Manejo de errores
- Validación: siempre pasar por `SQLValidator`; mostrar regla infringida.
- Errores DB: mensaje corto + hint; no exponer stacktrace.
- Timeouts: sugerir bajar `limit`/`timeout` o filtrar.

## UI y accesibilidad
- Rich con colores desactivables (`--plain`); prompts claros; spinner para LLM/DB.
- Formatos: tabla, JSON (`/set format=json`), texto plano.
- Logs en `logs/` con nivel configurable; token/latencia opcionales en pie.
