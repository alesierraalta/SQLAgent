# LLM Data Warehouse MVP

Sistema que traduce lenguaje natural a SQL complejo para PostgreSQL usando LangChain, con validación estricta de seguridad, schema estático, e interfaz CLI.

## Características

- **Traducción de lenguaje natural a SQL**: Convierte preguntas en español/inglés a queries SQL complejas (JOINs, CTEs, window functions)
- **Validación estricta**: Previene comandos peligrosos (DROP, INSERT, UPDATE, DELETE) y solo permite acceso a tablas/columnas del schema estático
- **Interfaz CLI moderna**: Usa Click y Rich para una experiencia de usuario excelente
- **Connection pooling**: Optimizado para múltiples consultas concurrentes
- **Retry logic**: Reintentos automáticos con exponential backoff para mayor robustez

## Requisitos

- Python 3.8+
- PostgreSQL (o cualquier base de datos compatible con SQLAlchemy)
- API key del proveedor de LLM (OpenAI/Anthropic/Google)

## Instalación

1. **Clonar o descargar el proyecto**

2. **Crear entorno virtual**:
   ```bash
   python -m venv .venv
   ```

3. **Activar entorno virtual**:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`

4. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Generar datos de prueba (opcional pero recomendado)**:
   ```bash
   python scripts/generate_test_data.py
   ```
   
   Este script creará las tablas `products` y `sales` con datos de prueba.
   **Nota**: Asegúrate de que PostgreSQL esté corriendo y que las credenciales en el script sean correctas.

6. **Configurar variables de entorno**:
   ```bash
   cp .env.example .env
   ```
   
   Editar `.env` y configurar:
   ```env
   # LLM (multi-proveedor)
   LLM_PROVIDER=openai  # openai|anthropic|google (gemini)
   LLM_MODEL=           # recomendado para no-openai
   OPENAI_API_KEY=tu_api_key_aqui
   ANTHROPIC_API_KEY=
   GOOGLE_API_KEY=
   DATABASE_URL=postgresql://postgres:050403@localhost:5432/postgres
   OPENAI_MODEL=gpt-4o
   MAX_QUERY_ROWS=1000
   QUERY_TIMEOUT=30
   LOG_LEVEL=INFO
   CACHE_TTL_SECONDS=3600
   SCHEMA_DISCOVERY=true
   ```
   
   **Opciones de Cache y Schema**:
   - `CACHE_TTL_SECONDS`: Tiempo de vida del cache de resultados (default: 3600 = 1 hora)
   - `SCHEMA_DISCOVERY`: Si `true`, descubre schema automáticamente desde PostgreSQL (default: `true`)
   
   **Optimizaciones de Tokens y Latencia**:
   - `USE_COMPACT_SCHEMA`: Usar formato compacto de schema (reduce tokens 60-70%, default: `true`)
   - `ENABLE_SEMANTIC_CACHE`: Habilitar cache semántico para queries similares (default: `true`)
   - `SEMANTIC_CACHE_THRESHOLD`: Threshold de similitud para cache semántico (0.0-1.0, default: `0.90`)
   - `USE_FAST_MODEL`: Usar gpt-4o-mini para queries simples (default: `true`)
   - `FAST_MODEL`: Modelo para queries simples (default: `gpt-4o-mini`)
   - `COMPLEX_MODEL`: Modelo para queries complejas (default: `gpt-4o`)
   - `ENABLE_FEW_SHOT`: Incluir ejemplos few-shot en prompts (default: `true`)
   - `ENABLE_PROMPT_CACHING`: Habilitar prompt caching de OpenAI (default: `true`)
   - `EMBEDDING_MODEL`: Modelo de embeddings para semantic cache (default: `all-MiniLM-L6-v2`)
   - `SCHEMA_MAX_TABLES`: Número máximo de tablas candidatas en el prompt compacto (default: 6)
   - `QUERY_TIMEOUT`: Timeout en segundos para consultas (se aplica como `statement_timeout` en Postgres).
   - `DEFAULT_TRANSACTION_READ_ONLY`: Forzado vía conexión a modo lectura (aplicado en la configuración del engine).
   
   **Nota**: Ajusta `DATABASE_URL` según tu configuración de PostgreSQL.
   
   **Proveedor de LLM (multi-proveedor)**:
   - `LLM_PROVIDER`: `openai` (default), `anthropic`, `google`/`gemini`
   - `LLM_MODEL`: modelo por defecto del proveedor (recomendado para `anthropic` y `google`)
   - Keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` (o `LLM_API_KEY` como alias)
   - Requisito: el modelo debe soportar tool/function calling (el flujo ejecuta SQL vía tools).

## Uso

### Comando Principal: Query

Ejecuta una consulta en lenguaje natural:

```bash
python -m src.cli query "¿Cuál es el total de revenue por país en enero?"
```

Opciones:
- `--verbose, -v`: Muestra detalles adicionales (SQL generado, tiempo de ejecución)
- `--explain, -e`: Explica qué hace el SQL antes de ejecutarlo
- `--stream, -s`: Streaming de resultados (útil para queries grandes)
- `--limit, -l`: Límite de resultados
- `--format, -f`: Formato de salida (table/json)
- `--export`: Exportar resultados a archivo (csv/json/excel)

Ejemplo con opciones:
```bash
python -m src.cli query "Muestra los top 10 productos por ventas" --limit 10 --verbose
```

### Ver Schema

Muestra el schema de la base de datos disponible:

```bash
python -m src.cli schema
```

### Probar Conexión

Verifica la conexión a la base de datos:

```bash
python -m src.cli test-connection
```

### Validar SQL Manualmente

Valida una query SQL antes de ejecutarla:

```bash
python -m src.cli validate-sql "SELECT * FROM sales WHERE revenue > 1000"
```

### Estadísticas de Performance

Muestra estadísticas de performance de queries ejecutadas:

```bash
python -m src.cli stats
```

Opciones:
- `--days, -d`: Número de días hacia atrás para analizar (default: 7)
- `--slow-threshold`: Threshold en segundos para queries lentas (default: 5.0)
- `--clear`: Limpiar todas las métricas

El comando muestra:
- Estadísticas generales (total queries, éxito, tiempos)
- Tokens promedio (si está disponible)
- Cache hit rate (semantic + SQL cache)
- Distribución de modelos usados
- Top queries lentas
- Patrones de queries más frecuentes
- `--clear`: Limpiar todas las métricas

### API HTTP (FastAPI) (experimental)

Levanta el backend HTTP (útil para integrar un frontend web):

```bash
uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

O como módulo:

```bash
python -m src.api
```

Healthcheck:
- `GET http://127.0.0.1:8000/api/v1/health`

Endpoints principales:
- `POST http://127.0.0.1:8000/api/v1/query` (single-shot)
- `GET http://127.0.0.1:8000/api/v1/query/stream?question=...` (SSE streaming)
- `GET http://127.0.0.1:8000/api/v1/schema`
- `GET http://127.0.0.1:8000/api/v1/history`
- `POST http://127.0.0.1:8000/api/v1/history/clear`
- `GET http://127.0.0.1:8000/api/v1/stats`
- `POST http://127.0.0.1:8000/api/v1/validate-sql`

### Frontend Web (Next.js)

Scaffold en `frontend/` (App Router + Tailwind). Ejecución local:

```bash
cd frontend
npm install
npm run dev
```

Variables:
- Backend: `WEB_ALLOWED_ORIGINS` (CSV) debe incluir `http://localhost:3000` (default).
- Frontend: `NEXT_PUBLIC_API_BASE_URL` (default: `http://127.0.0.1:8000/api/v1`).


## Configuración del Schema

El sistema soporta dos modos de carga de schema:

1. **Schema Discovery Automático** (recomendado): Descubre el schema automáticamente desde PostgreSQL usando SQLAlchemy Inspector. Activado por defecto (`SCHEMA_DISCOVERY=true`).

2. **Schema Estático**: Define el schema manualmente en `src/schemas/database_schema.py`. Útil si no tienes permisos de lectura en `information_schema` o prefieres control manual.

**IMPORTANTE**: Si usas schema estático, debes actualizar la función `_load_static_schema()` con el schema real de tu base de datos PostgreSQL.

Ejemplo de cómo definir tu schema:

```python
def load_schema() -> DatabaseSchema:
    return DatabaseSchema(
        tables={
            "tu_tabla": TableSchema(
                name="tu_tabla",
                description="Descripción de la tabla",
                columns=[
                    ColumnSchema(name="id", type="INTEGER", nullable=False),
                    ColumnSchema(name="nombre", type="VARCHAR(200)", nullable=False),
                    # ... más columnas
                ],
                primary_key=["id"],
                foreign_keys={"otra_col": "otra_tabla.id"},
            ),
            # ... más tablas
        }
    )
```

## Arquitectura

```
llm-dw-mvp/
├── src/
│   ├── agents/          # Agentes LangChain
│   │   └── sql_agent.py
│   ├── validators/       # Validadores SQL
│   │   └── sql_validator.py
│   ├── schemas/         # Schema estático
│   │   └── database_schema.py
│   ├── utils/           # Utilidades
│   │   ├── database.py
│   │   ├── exceptions.py
│   │   ├── history.py
│   │   └── logger.py
│   └── cli.py           # Interfaz CLI
├── tests/               # Tests
├── scripts/             # Scripts de utilidad
├── requirements.txt
└── README.md
```

### Diagrama de Arquitectura

Ver [ARQUITECTURA.md](ARQUITECTURA.md) para diagramas detallados en Mermaid que incluyen:
- Arquitectura completa del sistema
- Flujo de ejecución secuencial
- Componentes y responsabilidades
- Capas de seguridad
- Estructura de archivos
- Tecnologías y dependencias

### Flujo de Ejecución

1. Usuario hace pregunta en lenguaje natural vía CLI
2. CLI carga configuración y schema (descubrimiento automático o estático)
3. Se crea agente LangChain con herramientas SQL (tool_choice="any" para ejecución automática)
4. Agente genera SQL usando LLM (OpenAI GPT-4o)
5. Validador verifica SQL contra schema y reglas de seguridad
6. Si válido, se verifica cache antes de ejecutar
7. Si no está en cache, se ejecuta query en PostgreSQL
8. Si falla, se intenta recuperación automática del error
9. Resultados se formatean (tablas Rich) y muestran al usuario
10. Query y métricas se guardan automáticamente (historial y performance)

## Optimizaciones de Tokens y Latencia

El sistema incluye múltiples optimizaciones para reducir tokens, latencia y coste:

### 1. Compresión de Schema
- Formato compacto que reduce tokens en 60-70%
- Mantiene toda la información crítica (PK, FK, tipos)
- Configurable via `USE_COMPACT_SCHEMA`
- Subset dinámico: se priorizan tablas candidatas según la pregunta (`SCHEMA_MAX_TABLES`, default 6) y luego se añade el schema completo compacto como respaldo. Esto reduce el prompt inicial sin perder cobertura.

### 2. Semantic Caching
- Cache semántico que detecta queries similares usando embeddings
- Reutiliza resultados para preguntas semánticamente similares
- Threshold configurable (`SEMANTIC_CACHE_THRESHOLD=0.90`)
- Reduce latencia en 80-90% para queries repetidas
- Embeddings cacheados por hash de pregunta; si Redis está disponible se almacenan en Redis, si no, en memoria.

### 3. Model Selection Inteligente
- Usa `gpt-4o-mini` para queries simples (40-60% más rápido)
- Usa `gpt-4o` para queries complejas (mayor precisión)
- Clasificación automática de complejidad
- Configurable via `USE_FAST_MODEL`

### 4. Few-shot Examples
- Ejemplos dinámicos relevantes al tipo de query
- Mejora precisión y reduce necesidad de explicaciones largas
- Configurable via `ENABLE_FEW_SHOT`

### 5. Prompt Caching
- Aprovecha el prompt caching automático de OpenAI
- Cachea prefijos >1024 tokens (schema + reglas)
- Configurable via `ENABLE_PROMPT_CACHING`

### 6. Reducción de coste y salida
- Solicita salidas tabulares/JSON cuando es posible para reducir tokens de salida.
- Análisis opcional: el formato table/json evita prosa extensa salvo que el usuario lo requiera.
- Límite de filas (`MAX_QUERY_ROWS`) y `QUERY_TIMEOUT` controlan el tamaño/tiempo de respuesta.

### Resultados Esperados
- Tiempo promedio: De ~11s a <5s para queries simples, <10s para complejas
- Tokens: Reducción de 40-60% en tokens de input
- Cache hit rate: >30% en uso normal
- Costo: Reducción de 30-50% para queries simples

## Características Avanzadas

### Cache de Resultados
- Cache automático basado en hash de SQL normalizado
- TTL configurable (default: 1 hora)
- Reduce carga en BD y mejora UX para queries repetidas
- Se puede desactivar historial en hosts sensibles con `DISABLE_HISTORY=true`; caches pueden limpiarse con `/clearcache` (chat) y `/clearhistory`.
- Pruebas de rendimiento mock (perf): verifican latencia de rutas de cache y agente con umbrales estrictos.
   - Ejecuta con `pytest -m perf -o addopts=` si deseas correr solo perf sin cobertura global.

### Schema Discovery Automático
- Descubrimiento automático del schema desde PostgreSQL
- No requiere actualizar código manualmente
- Fallback a schema estático si falla

### Recuperación Automática de Errores
- Analiza errores SQL y genera queries corregidas automáticamente
- Retry automático con query corregida
- Solo para errores recuperables (sintaxis, columnas, tablas)

Seguridad Operativa
- Flags sensibles: DISABLE_HISTORY para evitar guardar historial en host; USE_REDIS_CACHE puede desactivarse en entornos con datos sensibles; CACHE_BACKEND=memory|file como fallback seguro.
- Claves y secretos: gestionar OPENAI_API_KEY y DATABASE_URL vía env/secret manager; no loggear valores. Rotar según políticas.
- Validación estricta: whitelist de funciones, bloqueo de comandos mutantes y multi-statement; schema restringido.

### Streaming de Resultados
- Soporte para streaming de resultados en tiempo real
- Útil para queries grandes que retornan muchos datos
- Mejor UX con resultados inmediatos

### Monitoreo de Performance
- Tracking automático de queries lentas
- Análisis de patrones de uso
- Estadísticas agregadas y métricas de éxito/fallo

## Seguridad

El sistema implementa múltiples capas de seguridad:

1. **Validación estricta**: Solo comandos SELECT permitidos
2. **Whitelist de tablas/columnas**: Solo acceso a recursos definidos en schema
3. **Detección de comandos peligrosos**: Bloquea DROP, INSERT, UPDATE, DELETE, etc.
4. **Validación recursiva**: Valida subconsultas y CTEs
5. **Timeouts**: Previene queries que se ejecuten indefinidamente

## Testing

Ejecutar tests:

```bash
pytest
```

Con coverage:

```bash
pytest --cov=src --cov-report=html
```

El coverage mínimo requerido es 80%.

## Troubleshooting

### Error: "DATABASE_URL no está configurada"

**Solución**: Verifica que el archivo `.env` existe y contiene `DATABASE_URL` con el formato correcto:
```
DATABASE_URL=postgresql://usuario:password@host:puerto/nombre_db
```

### Error: "Error de conexión a la base de datos"

**Soluciones**:
1. Verifica que PostgreSQL esté corriendo
2. Verifica credenciales en `.env`
3. Prueba la conexión: `python -m src.cli test-connection`

### Error: "Tabla 'X' no está permitida"

**Solución**: Agrega la tabla al schema estático en `src/schemas/database_schema.py`

### Error: "Error en API de LLM"

**Soluciones**:
1. Verifica `LLM_PROVIDER` y la API key correspondiente (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY`)
2. Verifica que el modelo configurado (`LLM_MODEL` u `OPENAI_MODEL`) exista y soporte tool calling
3. Si usas OpenAI, verifica créditos y disponibilidad del modelo

### Queries muy lentas

**Soluciones**:
1. Ajusta `QUERY_TIMEOUT` en `.env` (default: 30 segundos)
2. Verifica índices en tu base de datos
3. Usa `LIMIT` en tus queries para reducir resultados

## Desarrollo

### Estructura de Código

- **Type hints**: Todas las funciones tienen type hints
- **Docstrings**: Google/NumPy style
- **Logging**: Configurado con niveles apropiados
- **Excepciones**: Excepciones personalizadas para mejor manejo de errores

### Agregar Nuevas Funcionalidades

1. **Nueva tabla al schema**: Edita `src/schemas/database_schema.py`
2. **Nuevo comando CLI**: Agrega función en `src/cli.py` con decorador `@cli.command()`
3. **Nueva validación**: Extiende `SQLValidator` en `src/validators/sql_validator.py`

## Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request


## Licencia

Este proyecto es de código abierto y está disponible bajo la licencia [MIT](LICENSE).

## Soporte

Para problemas o preguntas, abre un issue en el repositorio del proyecto.

---

## 📢 Post para LinkedIn

¡Si te gusta este proyecto, ayúdame a compartirlo! Aquí tienes un borrador enfocado en tu desarrollo personal como ingeniero de IA:

> **🧠 Construyendo puentes entre SQL y Lenguaje Natural: Mi viaje con Agentes de IA**
>
> Recientemente me propuse un reto técnico: diseñar un sistema capaz de democratizar el acceso a datos complejos sin comprometer la seguridad ni el rendimiento. Así nació **LLM Data Warehouse MVP**.
>
> Este proyecto no es solo un "traductor de texto a SQL"; es una implementación profunda de **patrones de arquitectura para IA**:
>
> 🧩 **Desafíos técnicos que resolví:**
> *   **Determinismo vs. Creatividad:** Implementé un `SQLValidator` estricto que asegura que el LLM nunca ejecute comandos peligrosos, manteniendo la flexibilidad del lenguaje natural.
> *   **Optimización de Costos y Latencia:** Integré un **Cache Semántico** (usando embeddings) para que las preguntas repetidas sean instantáneas y gratuitas.
> *   **Robustez:** Diseñé un sistema de **Retry Logic** y recuperación de errores donde el agente aprende y corrige su propia sintaxis SQL.
>
> 🛠️ **Tech Stack:** Python, LangChain, PostgreSQL, SQLAlchemy, OpenAI, y Rich CLI.
>
> Este desarrollo me ha permitido profundizar en la ingeniería detrás de los agentes autónomos y la observabilidad con OpenTelemetry.
>
> 👨‍💻 **Código Open Source:**
> [Link a tu repositorio GitHub]
>
> ¿Qué opinan sobre el uso de caches semánticos en producción? ¡Los leo en los comentarios! 👇
>
> #AI #MachineLearning #Python #DataEngineering #LLM #OpenSource #SoftwareArchitecture #DevOps
