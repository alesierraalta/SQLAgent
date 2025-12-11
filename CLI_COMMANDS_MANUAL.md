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

## 6) Notas de seguridad/validación
- Solo se permite un statement; no se aceptan `;` extra ni comentarios (`--`, `/* */`).
- Comandos peligrosos (DROP/INSERT/UPDATE/DELETE/ALTER/CREATE/TRUNCATE/COPY/SET/SHOW/etc.) bloqueados.
- Tablas/columnas validadas contra el schema cargado.

## 7) Troubleshooting rápido
- Conexión: `python -m src.cli test-connection`; verifica `DATABASE_URL`.
- Sin resultados esperados: ajusta rango de fechas en la consulta; revisa que la tabla `sales` tenga datos recientes.
- Si el agente genera SQL bloqueado, simplifica la petición o usa consultas directas como las de los ejemplos avanzados (una sola sentencia, sin comentarios).
