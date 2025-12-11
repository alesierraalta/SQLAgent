# Arquitectura (PlantUML)

## Diagrama de componentes (vista general)
```plantuml
@startuml
skinparam componentStyle rectangle
skinparam packageStyle rectangle
title LLM Data Warehouse - Componentes

actor User
cloud OpenAI
cloud Redis
database Postgres

package "CLI" {
  [src/cli.py] as cli
  [src/cli_chat.py] as chat
}

package "Agentes" {
  [sql_agent.py] as sql_agent
  [query_explainer.py] as query_explainer
  [error_recovery.py] as error_recovery
}

package "Validación" {
  [sql_validator.py] as sql_validator
  [function_validation.py] as function_validation
}

package "Schema" {
  [database_schema.py] as schema_loader
}

package "Utils" {
  [utils/database.py] as db_utils
  [utils/cache.py] as cache_utils
  [utils/semantic_cache.py] as semantic_cache
  [utils/redis_client.py] as redis_client
  [utils/history.py] as history_utils
  [utils/performance.py] as performance_utils
}

User --> cli : query NL
User --> chat : chat
cli --> sql_agent
chat --> sql_agent
sql_agent --> sql_validator
sql_agent --> function_validation
sql_agent --> cache_utils : SQL cache
sql_agent --> semantic_cache : semantic cache
sql_agent --> db_utils : ejecutar SELECT
sql_agent --> OpenAI : LLM
semantic_cache --> redis_client : opcional
cache_utils --> redis_client : opcional
db_utils --> Postgres
schema_loader --> sql_validator
schema_loader --> sql_agent : prompt schema
history_utils <- cli
history_utils <- chat
performance_utils <- cli
performance_utils <- sql_agent
redis_client --> Redis

@enduml
```

## Flujo de consulta (secuencia)
```plantuml
@startuml
skinparam sequenceArrowThickness 1
skinparam sequenceParticipant underline
title Flujo consulta CLI/chat
actor User
participant CLI as "CLI/Chat"
participant Agent as "sql_agent"
participant Validator as "SQLValidator"
participant Cache as "SQL/Semantic Cache"
participant DB as "Postgres"
participant LLM as "OpenAI"

User -> CLI : pregunta NL
CLI -> Agent : execute_query(question, metadata)
Agent -> Cache : semantic hit?
Cache --> Agent : result? (si hit)
Agent -> LLM : generar SQL (si no hit)
Agent -> Validator : validate(SQL)
Validator --> Agent : OK / error
Agent -> Cache : SQL cache hit?
Cache --> Agent : result? (si hit)
Agent -> DB : ejecutar SELECT
DB --> Agent : filas
Agent -> Cache : set SQL/semantic
Agent --> CLI : respuesta + metadata
CLI --> User : tabla / análisis
@enduml
```

## Descubrimiento y schema compacto
```plantuml
@startuml
title Carga de schema y subset para prompt
participant SchemaLoader as "database_schema.py"
participant Agent
participant Validator
database Postgres

Agent -> SchemaLoader : load_schema()
alt discovery
  SchemaLoader -> Postgres : inspect schema (SCHEMA_DISCOVERY=true)
  Postgres --> SchemaLoader : tablas/columnas
  SchemaLoader -> SchemaLoader : cache TTL (SCHEMA_TTL_SECONDS)
end
Agent -> SchemaLoader : get_schema_for_prompt_compact()
Agent -> Agent : seleccionar tablas candidatas (SCHEMA_MAX_TABLES)
Agent -> Validator : init con schema
@enduml
```

## Manejo de errores y recuperación
```plantuml
@startuml
title Recuperación de errores SQL
participant Agent
participant Recovery as "error_recovery.py"
participant Validator
participant DB

Agent -> DB : ejecutar SQL
DB --> Agent : error
Agent -> Recovery : should_attempt_recovery(error)
alt recuperable
  Agent -> Recovery : recover_from_error(sql, error, schema)
  Recovery --> Agent : sql_corregido
  Agent -> Validator : validate(sql_corregido)
  Validator --> Agent : OK
  Agent -> DB : ejecutar corregida
  DB --> Agent : resultado / error
else no recuperable
  Agent --> CLI : mensaje de error
end
@enduml
```

## Caché y rendimiento
```plantuml
@startuml
title Cache y mediciones
participant Agent
participant SQLCache as "utils/cache.py"
participant SemanticCache as "utils/semantic_cache.py"
participant Perf as "utils/performance.py"
participant Redis

Agent -> SQLCache : get(sql_hash)
SQLCache --> Agent : hit/miss
Agent -> SemanticCache : get(question)
SemanticCache --> Agent : hit/miss
SemanticCache -> Redis : opcional set/get
SQLCache -> Redis : opcional set/get
Agent -> Perf : record_query_performance(sql, time, cache_hit_type, tokens)
@enduml
```
