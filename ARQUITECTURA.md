# Arquitectura del Sistema LLM-DW MVP

## Diagrama de Arquitectura

```mermaid
graph TB
    subgraph "Usuario"
        USER[👤 Usuario]
    end

    subgraph "Interfaz CLI"
        CLI[CLI<br/>src/cli.py<br/>Click + Rich]
        CLI -->|Comandos| QUERY[query]
        CLI -->|Comandos| SCHEMA[schema]
        CLI -->|Comandos| VALIDATE[validate-sql]
        CLI -->|Comandos| HISTORY[history]
        CLI -->|Comandos| TEST[test-connection]
    end

    subgraph "Capa de Agente"
        AGENT[SQL Agent<br/>src/agents/sql_agent.py]
        AGENT -->|Crea| LLM[ChatOpenAI<br/>gpt-4o]
        AGENT -->|Usa| TOOLKIT[SQLDatabaseToolkit]
        AGENT -->|Genera| PROMPT[System Prompt<br/>Dinámico con Schema]
        AGENT -->|Ejecuta| EXECUTE[execute_query<br/>Retry Logic]
    end

    subgraph "Capa de Validación"
        VALIDATOR[SQL Validator<br/>src/validators/sql_validator.py]
        VALIDATOR -->|Valida| DANGER[Dangerous Commands]
        VALIDATOR -->|Extrae| TABLES[Tablas]
        VALIDATOR -->|Extrae| COLUMNS[Columnas]
        VALIDATOR -->|Valida| SUBQUERIES[Subconsultas/CTEs]
    end

    subgraph "Capa de Datos"
        DB_UTILS[Database Utils<br/>src/utils/database.py]
        DB_UTILS -->|Crea| ENGINE[SQLAlchemy Engine<br/>Connection Pooling]
        ENGINE -->|Conecta| POSTGRES[(PostgreSQL<br/>Data Warehouse)]
    end

    subgraph "Capa de Schema"
        SCHEMA_MODULE[Database Schema<br/>src/schemas/database_schema.py]
        SCHEMA_MODULE -->|Define| STATIC_SCHEMA[Schema Estático<br/>Pydantic Models]
        STATIC_SCHEMA -->|Contiene| TABLES_SCHEMA[Tablas Permitidas]
        STATIC_SCHEMA -->|Contiene| COLUMNS_SCHEMA[Columnas Permitidas]
    end

    subgraph "Utilidades"
        HISTORY_UTIL[History<br/>src/utils/history.py]
        LOGGER[Logger<br/>src/utils/logger.py]
        EXCEPTIONS[Exceptions<br/>src/utils/exceptions.py]
    end

    subgraph "Servicios Externos"
        OPENAI[OpenAI API<br/>GPT-4o]
        POSTGRES
    end

    %% Flujo principal
    USER -->|Pregunta Natural| CLI
    QUERY -->|Carga| SCHEMA_MODULE
    QUERY -->|Obtiene| ENGINE
    QUERY -->|Crea| AGENT
    
    AGENT -->|Genera SQL| LLM
    LLM -->|API Call| OPENAI
    LLM -->|SQL Generado| VALIDATOR
    
    VALIDATOR -->|Consulta| STATIC_SCHEMA
    VALIDATOR -->|Valida| TABLES_SCHEMA
    VALIDATOR -->|Valida| COLUMNS_SCHEMA
    
    VALIDATOR -->|SQL Válido| TOOLKIT
    TOOLKIT -->|Ejecuta| ENGINE
    ENGINE -->|Query| POSTGRES
    POSTGRES -->|Resultados| ENGINE
    ENGINE -->|Datos| TOOLKIT
    TOOLKIT -->|Respuesta| AGENT
    AGENT -->|Formatea| CLI
    CLI -->|Muestra| USER
    
    %% Guardado en historial
    QUERY -->|Guarda| HISTORY_UTIL
    HISTORY_UTIL -->|Persiste| HISTORY_FILE[(Historial<br/>~/.llm_dw_history.json)]
    
    %% Logging
    AGENT -->|Logs| LOGGER
    VALIDATOR -->|Logs| LOGGER
    DB_UTILS -->|Logs| LOGGER
    
    %% Manejo de errores
    VALIDATOR -->|Errores| EXCEPTIONS
    DB_UTILS -->|Errores| EXCEPTIONS
    AGENT -->|Errores| EXCEPTIONS
    
    %% Validación manual
    VALIDATE -->|Valida SQL| VALIDATOR
    
    %% Estilos
    classDef userClass fill:#e1f5ff,stroke:#01579b,stroke-width:2px
    classDef cliClass fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef agentClass fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef validatorClass fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef dataClass fill:#e0f2f1,stroke:#004d40,stroke-width:2px
    classDef schemaClass fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef utilClass fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    classDef externalClass fill:#ffebee,stroke:#b71c1c,stroke-width:2px
    
    class USER userClass
    class CLI,QUERY,SCHEMA,VALIDATE,HISTORY,TEST cliClass
    class AGENT,LLM,TOOLKIT,PROMPT,EXECUTE agentClass
    class VALIDATOR,DANGER,TABLES,COLUMNS,SUBQUERIES validatorClass
    class DB_UTILS,ENGINE,POSTGRES dataClass
    class SCHEMA_MODULE,STATIC_SCHEMA,TABLES_SCHEMA,COLUMNS_SCHEMA schemaClass
    class HISTORY_UTIL,LOGGER,EXCEPTIONS utilClass
    class OPENAI externalClass
```

## Flujo de Ejecución Detallado

```mermaid
sequenceDiagram
    participant U as Usuario
    participant CLI as CLI
    participant Schema as DatabaseSchema
    participant DB as Database Utils
    participant Agent as SQL Agent
    participant LLM as OpenAI GPT-4o
    participant Validator as SQL Validator
    participant PG as PostgreSQL

    U->>CLI: query "¿Total revenue por país?"
    CLI->>Schema: load_schema()
    Schema-->>CLI: DatabaseSchema
    CLI->>DB: get_db_engine()
    DB-->>CLI: SQLAlchemy Engine
    CLI->>Agent: create_sql_agent(engine, schema)
    
    Note over Agent: Crea LLM con tool_choice="any"
    Note over Agent: Crea validated_sql_query tool
    Note over Agent: Genera system prompt con schema
    
    Agent-->>CLI: Agent configurado
    CLI->>Agent: execute_query(agent, question)
    
    Agent->>LLM: invoke(pregunta)
    LLM->>LLM: Genera SQL
    LLM-->>Agent: AIMessage con tool_call
    
    Agent->>Validator: validate_query(sql)
    Validator->>Validator: Extrae tablas
    Validator->>Validator: Extrae columnas
    Validator->>Schema: validate_table/column
    Schema-->>Validator: ✓ Válido
    
    Validator-->>Agent: SQL válido
    Agent->>PG: Ejecuta query
    PG-->>Agent: Resultados
    Agent-->>CLI: Respuesta formateada
    CLI->>CLI: _format_query_result()
    CLI->>U: Muestra tabla Rich
```

## Componentes y Responsabilidades

```mermaid
graph LR
    subgraph "Módulos Principales"
        A[CLI<br/>Interfaz Usuario]
        B[SQL Agent<br/>Orquestación LLM]
        C[SQL Validator<br/>Seguridad]
        D[Database Utils<br/>Conexiones]
        E[Database Schema<br/>Whitelist]
        F[History<br/>Persistencia]
    end
    
    subgraph "Funcionalidades"
        A1[Comandos CLI]
        A2[Formateo Resultados]
        A3[Exportación]
        
        B1[Generación SQL]
        B2[Ejecución Automática]
        B3[Retry Logic]
        
        C1[Validación Tablas]
        C2[Validación Columnas]
        C3[Detección Comandos Peligrosos]
        
        D1[Connection Pooling]
        D2[Timeout Management]
        
        E1[Schema Estático]
        E2[Validación Whitelist]
        
        F1[Guardado Queries]
        F2[Historial]
    end
    
    A --> A1
    A --> A2
    A --> A3
    B --> B1
    B --> B2
    B --> B3
    C --> C1
    C --> C2
    C --> C3
    D --> D1
    D --> D2
    E --> E1
    E --> E2
    F --> F1
    F --> F2
```

## Capas de Seguridad

```mermaid
graph TD
    SQL[SQL Generado] --> L1[Capas de Validación]
    
    L1 --> L2[1. Detección Comandos Peligrosos<br/>DROP, INSERT, UPDATE, DELETE]
    L2 -->|Bloquea| REJECT1[❌ Rechazado]
    L2 -->|Permite SELECT| L3
    
    L3[2. Validación de Tablas<br/>Whitelist Schema]
    L3 -->|Tabla no permitida| REJECT2[❌ Rechazado]
    L3 -->|Tabla válida| L4
    
    L4[3. Validación de Columnas<br/>Whitelist Schema]
    L4 -->|Columna no permitida| REJECT3[❌ Rechazado]
    L4 -->|Columnas válidas| L5
    
    L5[4. Validación Recursiva<br/>Subconsultas y CTEs]
    L5 -->|Error en subconsulta| REJECT4[❌ Rechazado]
    L5 -->|Todo válido| L6
    
    L6[5. Timeout Protection<br/>QUERY_TIMEOUT]
    L6 -->|Timeout| REJECT5[❌ Rechazado]
    L6 -->|Dentro de tiempo| ACCEPT[✅ Aceptado y Ejecutado]
    
    style REJECT1 fill:#ffcdd2
    style REJECT2 fill:#ffcdd2
    style REJECT3 fill:#ffcdd2
    style REJECT4 fill:#ffcdd2
    style REJECT5 fill:#ffcdd2
    style ACCEPT fill:#c8e6c9
```

## Estructura de Archivos

```mermaid
graph TD
    ROOT[llm-dw-mvp/] --> SRC[src/]
    ROOT --> TESTS[tests/]
    ROOT --> SCRIPTS[scripts/]
    ROOT --> DOCS[Documentación]
    
    SRC --> CLI[cli.py<br/>Interfaz CLI]
    SRC --> AGENTS[agents/]
    SRC --> VALIDATORS[validators/]
    SRC --> SCHEMAS[schemas/]
    SRC --> UTILS[utils/]
    
    AGENTS --> AGENT_FILE[sql_agent.py<br/>create_sql_agent<br/>execute_query]
    
    VALIDATORS --> VALIDATOR_FILE[sql_validator.py<br/>SQLValidator<br/>Validación Estricta]
    
    SCHEMAS --> SCHEMA_FILE[database_schema.py<br/>DatabaseSchema<br/>Schema Estático]
    
    UTILS --> DB_UTIL[database.py<br/>Connection Pooling]
    UTILS --> EXCEPTIONS_UTIL[exceptions.py<br/>Excepciones Personalizadas]
    UTILS --> LOGGER_UTIL[logger.py<br/>Logging Configurado]
    UTILS --> HISTORY_UTIL[history.py<br/>Gestión Historial]
    
    TESTS --> TEST_AGENT[test_agent.py]
    TESTS --> TEST_VALIDATOR[test_validator.py]
    TESTS --> TEST_CLI[test_cli.py]
    TESTS --> TEST_DB[test_database.py]
    TESTS --> TEST_HISTORY[test_history.py]
    
    SCRIPTS --> GEN_DATA[generate_test_data.py<br/>Datos de Prueba]
```

## Tecnologías y Dependencias

```mermaid
graph LR
    APP[Aplicación Python] --> LANGCHAIN[LangChain<br/>Agentes y Tools]
    APP --> SQLALCHEMY[SQLAlchemy 2.0+<br/>ORM y Pooling]
    APP --> OPENAI_PY[OpenAI API<br/>GPT-4o]
    APP --> CLICK[Click<br/>CLI Framework]
    APP --> RICH[Rich<br/>UI Terminal]
    APP --> SQLPARSE[sqlparse<br/>Parsing SQL]
    APP --> PYDANTIC[Pydantic<br/>Validación Schema]
    
    LANGCHAIN --> OPENAI_API[OpenAI API]
    SQLALCHEMY --> POSTGRES_DRIVER[psycopg2<br/>PostgreSQL Driver]
    
    style APP fill:#e3f2fd
    style LANGCHAIN fill:#fff3e0
    style SQLALCHEMY fill:#e8f5e9
    style OPENAI_PY fill:#fce4ec
```
