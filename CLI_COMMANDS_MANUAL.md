# Manual rápido de comandos CLI y escenarios útiles

> Ejecuta siempre con el entorno activado (`.venv\Scripts\activate`) y `.env` configurado.

## 1) Consultas en lenguaje natural
- Básico:  
  `python -m src.cli query "¿Cuál es el revenue total?"`
- Con explicación del SQL antes de ejecutar:  
  `python -m src.cli query "Promedio móvil de revenue 7 días para los últimos 30" --explain`
- Límite de filas:  
  `python -m src.cli query "Top 10 productos por revenue" --limit 10`
- Formato JSON:  
  `python -m src.cli query "Ventas por país" --format json`
- Exportar resultados:  
  `python -m src.cli query "Ventas por país" --export resultados.csv`
- Streaming (para respuestas grandes):  
  `python -m src.cli query "Detalle de ventas últimos 30 días" --stream`

## 2) Validación y seguridad
- Validar SQL manualmente (sin ejecutar):  
  `python -m src.cli validate-sql "SELECT country, SUM(revenue) FROM sales GROUP BY country"`
- Ver schema cargado:  
  `python -m src.cli schema`
- Probar conexión a la BD:  
  `python -m src.cli test-connection`

## 3) Historial y stats
- Ver historial de consultas:  
  `python -m src.cli history`
- Estadísticas de performance (últimos 7 días por defecto):  
  `python -m src.cli stats`
- Stats con umbral de lentitud:  
  `python -m src.cli stats --slow-threshold 5`
- Limpiar estadísticas:  
  `python -m src.cli stats --clear`

## 4) Ejemplos avanzados (según base de datos de ventas genérica)
- Comparación de revenue (últimos 90 vs 90 previos):  
  `python -m src.cli query "Calcula el revenue total de los últimos 90 días y compáralo vs los 90 días anteriores" --explain`
- Top 5 países por share global (último trimestre):  
  `python -m src.cli query "Top 5 países por revenue en el último trimestre y su share del total" --explain`
- Revenue mensual con delta por categoría:  
  `python -m src.cli query "Revenue mensual y crecimiento vs mes anterior por categoría" --explain`
- Productos sin ventas últimos 90 días:  
  `python -m src.cli query "Productos sin ventas en los últimos 90 días" --explain`
- Top 10 productos por crecimiento vs mes previo:  
  `python -m src.cli query "Top 10 productos por crecimiento de revenue vs mes anterior" --explain`

## 5) Flags/entorno relevantes
- `QUERY_TIMEOUT`: timeout (s) que se aplica como `statement_timeout` en Postgres.
- Modo lectura: conexiones configuradas como read-only por defecto.
- Cache semántico: `ENABLE_SEMANTIC_CACHE` (`true/false`).
- Modelos: `OPENAI_MODEL`, `FAST_MODEL`, `COMPLEX_MODEL`.
- Redis/cache distribuido: `USE_REDIS_CACHE=true`, `CACHE_BACKEND=redis`, `REDIS_URL=redis://localhost:6379/0` (ver sección Docker).
- Prompt compacto: `SCHEMA_MAX_TABLES` controla cuántas tablas candidatas se incluyen en el prompt (default 6) para reducir tokens.
- Embeddings: `EMBEDDING_MODEL` (default `all-MiniLM-L6-v2`); embeddings cacheados por hash de pregunta. Si Redis está activo, se usan para cache distribuido.

## 6) Notas de seguridad/validación
- Solo se permite un statement; no se aceptan `;` extra ni comentarios (`--`, `/* */`).
- Comandos peligrosos (DROP/INSERT/UPDATE/DELETE/ALTER/CREATE/TRUNCATE/COPY/SET/SHOW/etc.) bloqueados.
- Tablas/columnas validadas contra el schema cargado.

## 7) Troubleshooting rápido
- Conexión: `python -m src.cli test-connection`; verifica `DATABASE_URL`.
- Sin resultados esperados: ajusta rango de fechas en la consulta; revisa que la tabla `sales` tenga datos recientes.
- Si el agente genera SQL bloqueado, simplifica la petición o usa consultas directas como las de los ejemplos avanzados (una sola sentencia, sin comentarios).

## 8) Cache con Redis (Docker) para menor latencia
- Levantar Redis: `docker compose up -d redis`.
- Entorno local: `set CACHE_BACKEND=redis`, `set USE_REDIS_CACHE=true`, `set REDIS_URL=redis://localhost:6379/0`.
- Efecto: cache SQL y semántico persisten entre sesiones; hits reducen llamadas a LLM/DB.
- Chat CLI: usa `/clearcache` para limpiar; repite un prompt para ver `cache=sql` o `cache=semantic` en la metadata.

## 9) Modo sin Redis
- Desactiva cache distribuido: `set USE_REDIS_CACHE=false` y/o `set CACHE_BACKEND=memory` (por defecto).
- Deja `REDIS_URL` vacío o sin definir.
- El sistema usará cache en memoria/archivo; no intentará conectarse a Redis.

## 10) Chat CLI (modo conversación)
- Lanzar: `python -m src.cli_chat --mode safe`.
- Comandos clave: `/config` (editar mode/format/limit/timeout), `/schema`, `/settings`, `/history`, `/retry`, `/sql`, `/export path`, `/clear`, `/clearcache`, `/exit`.
- Autocompletado: escribe `/` y usa Tab para ver comandos con descripción.
- Al cerrar (Ctrl+C o `/exit`), muestra resumen de sesión (queries, cache hits, tokens).
