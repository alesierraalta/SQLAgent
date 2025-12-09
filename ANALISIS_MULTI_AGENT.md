# Análisis Arquitectónico: Integración de Multi-Agent System (Patrón ADK)

## 📋 Resumen Ejecutivo

**Recomendación:** **NO implementar multi-agent system en el estado actual del proyecto**, pero **SÍ documentar la arquitectura evolutiva** para futuras expansiones.

**Razón Principal:** El sistema actual ya implementa optimizaciones equivalentes (model selection, caching, error recovery) que resuelven los problemas que multi-agent abordaría, sin añadir la complejidad adicional.

---

## 🔍 Análisis de la Arquitectura Actual

### Estado Actual del Sistema

El sistema LLM-DW MVP tiene la siguiente arquitectura:

```
Usuario → CLI → SQL Agent (LangChain) → LLM (GPT-4o/gpt-4o-mini) → SQL Validator → PostgreSQL
```

**Componentes Clave:**
- **Agente Único:** `create_sql_agent()` en `src/agents/sql_agent.py`
- **Model Selection Inteligente:** Clasifica queries simples vs complejas y usa `gpt-4o-mini` o `gpt-4o` según corresponda
- **Error Recovery:** Función `recover_from_error()` que usa LLM para corregir SQL fallido
- **Caching Multi-nivel:** SQL cache (hash-based) + Semantic cache (embeddings)
- **Validación Estricta:** `SQLValidator` con whitelist de tablas/columnas
- **Optimizaciones:** Schema compression, few-shot examples, prompt caching

### Fortalezas del Sistema Actual

1. **Simplicidad:** Flujo directo y fácil de entender
2. **Optimización de Costos:** Model selection reduce costos en queries simples
3. **Baja Latencia:** Sin overhead de delegación entre agentes
4. **Mantenibilidad:** Código simple y bien estructurado
5. **Robustez:** Error recovery y validación estricta

### Limitaciones Identificadas

1. **Monolítico:** Un solo agente maneja todos los tipos de queries
2. **Sin Especialización:** Mismo prompt para queries analíticas, exploratorias, reportes
3. **Escalabilidad Limitada:** Agregar nuevos tipos de queries requiere modificar el agente principal
4. **Sin Paralelización:** No puede procesar múltiples queries simultáneamente

---

## 🏗️ Arquitectura Multi-Agent (Patrón ADK)

### Conceptos Clave de ADK Multi-Agent

**1. Root Agent (Orquestador)**
- Recibe la petición inicial del usuario
- Analiza la intención usando LLM
- Decide a qué sub-agente delegar basándose en `description` de cada sub-agent
- Puede manejar tareas directamente si no hay sub-agent apropiado

**2. Sub-Agents (Especializados)**
- Cada uno tiene un propósito específico claramente definido
- Instrucciones (`instruction`) optimizadas para su dominio
- Herramientas (`tools`) específicas para su tarea
- Descripción (`description`) que el root agent usa para delegación

**3. Delegación Automática (Auto-Flow)**
- El root agent usa su LLM para decidir delegación
- Basado en matching semántico entre query del usuario y `description` de sub-agents
- No requiere código explícito de routing

**4. Session State Compartido**
- Todos los agentes comparten el mismo `session.state`
- Permite contexto compartido entre agentes
- Herramientas pueden leer/escribir estado

### Ejemplo de Arquitectura Multi-Agent para SQL

```python
# Root Agent (Orquestador)
root_agent = Agent(
    name="sql_coordinator",
    description="Coordina queries SQL y delega a especialistas",
    instruction="Analiza la query y delega a: analytics_agent (agregaciones), 
                 exploration_agent (exploración de datos), reporting_agent (reportes)",
    sub_agents=[analytics_agent, exploration_agent, reporting_agent]
)

# Sub-Agent: Analytics
analytics_agent = Agent(
    name="analytics_agent",
    description="Genera queries SQL para análisis agregados (SUM, COUNT, GROUP BY)",
    instruction="Especialista en queries analíticas. Genera SQL optimizado para agregaciones...",
    tools=[validated_sql_query],
    model="gpt-4o-mini"  # Modelo más barato para queries simples
)

# Sub-Agent: Exploration
exploration_agent = Agent(
    name="exploration_agent",
    description="Genera queries SQL para exploración de datos (JOINs, CTEs, subqueries)",
    instruction="Especialista en queries complejas. Genera SQL con JOINs, CTEs...",
    tools=[validated_sql_query],
    model="gpt-4o"  # Modelo más potente para complejidad
)
```

---

## ⚖️ Comparación: Sistema Actual vs Multi-Agent

### Tabla Comparativa

| Aspecto | Sistema Actual | Multi-Agent (ADK) |
|---------|---------------|-------------------|
| **Arquitectura** | Agente único monolítico | Root agent + sub-agents especializados |
| **Model Selection** | ✅ Clasificación automática (simple/complex) | ✅ Cada sub-agent puede usar modelo diferente |
| **Latencia** | ⚡ Baja (1 llamada LLM) | ⚠️ Media (2 llamadas: root + sub-agent) |
| **Costo por Query** | 💰 Optimizado (model selection) | ⚠️ Potencialmente mayor (root + sub-agent) |
| **Complejidad** | ✅ Baja | ⚠️ Alta (coordinación, debugging) |
| **Especialización** | ⚠️ Limitada (mismo prompt) | ✅ Alta (prompts específicos por dominio) |
| **Escalabilidad** | ⚠️ Requiere modificar agente principal | ✅ Fácil agregar nuevos sub-agents |
| **Mantenibilidad** | ✅ Simple | ⚠️ Compleja (múltiples agentes, estados) |
| **Paralelización** | ❌ No soportada | ✅ Posible (múltiples sub-agents) |
| **Error Recovery** | ✅ Implementado | ✅ Puede ser por sub-agent |
| **Caching** | ✅ Multi-nivel (SQL + semantic) | ✅ Compartido entre agentes |

### Análisis de Costos

**Sistema Actual:**
- Query simple: 1 llamada a `gpt-4o-mini` (~$0.15/1M tokens input)
- Query compleja: 1 llamada a `gpt-4o` (~$2.50/1M tokens input)

**Multi-Agent:**
- Query simple: 1 llamada root agent (`gpt-4o`) + 1 llamada sub-agent (`gpt-4o-mini`) = **2x costo**
- Query compleja: 1 llamada root agent (`gpt-4o`) + 1 llamada sub-agent (`gpt-4o`) = **2x costo**

**Conclusión:** Multi-agent **duplica el costo** de tokens porque requiere 2 llamadas LLM (root decide + sub-agent ejecuta).

### Análisis de Latencia

**Sistema Actual:**
- Query simple: ~2-5s (1 llamada LLM + ejecución SQL)
- Query compleja: ~5-15s (1 llamada LLM + ejecución SQL)

**Multi-Agent:**
- Query simple: ~4-10s (root agent ~2-3s + sub-agent ~2-5s + ejecución SQL)
- Query compleja: ~10-30s (root agent ~3-5s + sub-agent ~5-15s + ejecución SQL)

**Conclusión:** Multi-agent **aumenta la latencia** significativamente debido al overhead de delegación.

---

## 🎯 Casos de Uso Potenciales para Multi-Agent

### 1. Especialización por Tipo de Query

**Escenario:** Diferentes tipos de queries requieren diferentes enfoques:
- **Analytics Agent:** Queries agregadas (SUM, COUNT, GROUP BY)
- **Exploration Agent:** Queries con JOINs, CTEs, subqueries
- **Reporting Agent:** Queries para generar reportes estructurados
- **Visualization Agent:** Queries optimizadas para visualizaciones

**Evaluación:** 
- ✅ **Beneficio:** Prompts más específicos podrían mejorar precisión
- ❌ **Costo:** Duplica llamadas LLM y latencia
- ❌ **Alternativa Actual:** El sistema ya usa model selection y few-shot examples que logran similar especialización

### 2. Validación SQL como Agente Separado

**Escenario:** Un agente especializado solo en validación SQL antes de ejecutar.

**Evaluación:**
- ❌ **No Recomendado:** La validación actual es síncrona y rápida (~1ms). Convertirla en agente añadiría latencia innecesaria sin beneficios.

### 3. Optimización de Queries

**Escenario:** Un agente que analiza el SQL generado y lo optimiza antes de ejecutar.

**Evaluación:**
- ⚠️ **Potencialmente Útil:** Podría mejorar performance de queries complejas
- ❌ **Costo:** Añade otra llamada LLM
- ✅ **Alternativa:** Implementar como función post-procesamiento, no como agente

### 4. Explicación de Resultados

**Escenario:** Un agente especializado en explicar resultados de queries de forma inteligente.

**Evaluación:**
- ✅ **Útil:** Ya existe `explain_query()`, pero como agente podría ser más contextual
- ⚠️ **Costo:** Requiere llamada LLM adicional solo cuando se solicita explicación
- ✅ **Viable:** Solo si se activa bajo demanda (flag `--explain`)

### 5. Paralelización de Queries

**Escenario:** Múltiples queries simultáneas procesadas por diferentes sub-agents.

**Evaluación:**
- ✅ **Beneficio Real:** Permite procesar múltiples queries en paralelo
- ⚠️ **Complejidad:** Requiere gestión de concurrencia y recursos
- ❌ **Caso de Uso Actual:** El sistema es CLI single-user, no necesita paralelización

---

## 📊 Investigación de Mejores Prácticas

### Hallazgos de Investigación Web

1. **Multi-Agent vs Single-Agent para SQL Generation:**
   - Multi-agent mejora precisión en **tareas complejas** (hasta 40% según estudios)
   - Single-agent es más eficiente para **tareas simples**
   - El sistema actual ya clasifica simple vs complex, optimizando automáticamente

2. **Costos y Latencia:**
   - Multi-agent **duplica costos** (root + sub-agent)
   - Añade **overhead de latencia** (delegación requiere 2 llamadas LLM)
   - Solo justificable si los beneficios superan estos costos

3. **Arquitectura ADK vs LangChain:**
   - ADK: Hierárquico, event-driven, delegación LLM-driven
   - LangChain: Graph-based, message passing, control explícito
   - El sistema actual usa LangChain, migrar a ADK requeriría refactorización significativa

### Benchmarking de Sistemas Similares

**SQLGenie (Multi-Agent):**
- 64% reducción en tiempo de generación SQL
- Pero requiere múltiples agentes especializados y coordinación compleja

**Sistema Actual:**
- Ya optimizado con model selection (gpt-4o-mini para simples)
- Caching reduce latencia en queries repetidas
- Error recovery maneja casos complejos

**Conclusión:** Para el caso de uso actual (MVP SQL generation), el sistema actual es más eficiente.

---

## ✅ Recomendación Final

### Para el Estado Actual (MVP)

**NO implementar multi-agent** por las siguientes razones:

1. **Over-Engineering:** El sistema actual resuelve eficientemente el problema sin necesidad de multi-agent
2. **Costos Duplicados:** Multi-agent duplicaría costos de tokens sin beneficios claros
3. **Latencia Aumentada:** Añadiría overhead de delegación innecesario
4. **Complejidad Añadida:** Haría el código más difícil de mantener y debuggear
5. **Ya Optimizado:** Model selection, caching, y error recovery ya optimizan el sistema

### Para Evolución Futura

**SÍ documentar arquitectura evolutiva** que permita migrar a multi-agent cuando:

1. **El sistema crezca** para soportar múltiples tipos de consultas (analíticas, exploratorias, reportes, visualizaciones)
2. **Se requiera paralelización** de múltiples queries simultáneas
3. **Se necesite especialización profunda** en diferentes dominios (ej: queries financieras vs operacionales)
4. **El volumen de queries** justifique la inversión en arquitectura más compleja

### Arquitectura Evolutiva Propuesta (Futuro)

Si en el futuro se decide implementar multi-agent, la arquitectura recomendada sería:

```
Root Agent (Coordinator)
├── Analytics Agent (queries agregadas, gpt-4o-mini)
├── Exploration Agent (JOINs, CTEs, gpt-4o)
├── Reporting Agent (reportes estructurados, gpt-4o)
└── Visualization Agent (queries para charts, gpt-4o-mini)
```

**Patrón de Implementación:**
- Usar **LangChain AgentExecutor** con routing basado en clasificación de intención
- **NO adoptar ADK completo** (añadiría dependencias innecesarias)
- Implementar patrón similar a ADK pero con LangChain (compatibilidad con código actual)
- Mantener session state compartido para contexto entre agentes

---

## 🔄 Alternativa: Híbrido (Recomendado para Futuro)

### Arquitectura Híbrida con LangChain

En lugar de adoptar ADK completo, implementar un patrón similar usando LangChain:

```python
# Clasificador de Intención (sin LLM, basado en keywords)
def classify_query_intent(question: str) -> str:
    """Clasifica el tipo de query sin usar LLM"""
    # Analytics: SUM, COUNT, total, promedio
    # Exploration: JOIN, subquery, CTE
    # Reporting: reporte, resumen, dashboard
    # Visualization: gráfico, chart, visualizar
    ...

# Root Agent (solo para casos ambiguos)
root_agent = create_agent(...)  # Usa LLM solo si clasificación falla

# Sub-Agents Especializados
analytics_agent = create_sql_agent(..., model="gpt-4o-mini")
exploration_agent = create_sql_agent(..., model="gpt-4o")
reporting_agent = create_sql_agent(..., model="gpt-4o")
```

**Ventajas:**
- ✅ Mantiene compatibilidad con código actual
- ✅ Evita overhead de delegación LLM-driven (usa clasificación rápida)
- ✅ Permite especialización sin duplicar costos
- ✅ Fácil de implementar incrementalmente

**Cuándo Implementar:**
- Cuando se agreguen nuevos tipos de queries (reportes, visualizaciones)
- Cuando el volumen de queries justifique especialización
- Cuando se requiera paralelización

---

## 📝 Plan de Acción Recomendado

### Fase 1: Estado Actual (MVP) - ✅ Completado
- Mantener arquitectura actual (agente único)
- Optimizar con model selection, caching, error recovery
- **NO implementar multi-agent**

### Fase 2: Evolución Incremental (Futuro)
Si el sistema crece, implementar híbrido:

1. **Agregar Clasificador de Intención** (sin LLM)
   - Analytics vs Exploration vs Reporting
   - Basado en keywords y patrones

2. **Crear Sub-Agents Especializados** (solo si necesario)
   - Analytics Agent: para queries agregadas
   - Exploration Agent: para queries complejas
   - Mantener agente único si no hay necesidad real

3. **Implementar Routing Inteligente**
   - Clasificación rápida → routing directo a sub-agent
   - Evitar delegación LLM-driven para reducir latencia

### Fase 3: Multi-Agent Completo (Solo si Justificado)
Solo si:
- El sistema soporta múltiples dominios (finanzas, operaciones, marketing)
- Se requiere paralelización real
- El volumen justifica la complejidad

---

## 🎓 Lecciones Aprendidas de ADK

Aunque **NO recomendamos adoptar ADK completo**, los siguientes patrones de ADK son valiosos:

1. **Delegación Basada en Descripciones:** Usar `description` clara para routing
2. **Session State Compartido:** Contexto compartido entre componentes
3. **Especialización de Prompts:** Instrucciones específicas por dominio
4. **Model Selection por Agente:** Diferentes modelos según complejidad

Estos patrones pueden implementarse con LangChain sin necesidad de ADK.

---

## 📈 Métricas de Éxito para Decisión Futura

Implementar multi-agent solo si se cumplen **TODOS** estos criterios:

1. ✅ **Volumen:** >1000 queries/día que requieran diferentes especializaciones
2. ✅ **Diversidad:** >3 tipos distintos de queries (analytics, exploration, reporting, etc.)
3. ✅ **Paralelización:** Necesidad real de procesar múltiples queries simultáneamente
4. ✅ **Especialización:** Beneficios medibles de prompts especializados (>10% mejora en precisión)
5. ✅ **Recursos:** Equipo y tiempo para mantener arquitectura más compleja

**Si NO se cumplen estos criterios:** Mantener arquitectura actual.

---

## 🔗 Referencias y Recursos

- [ADK Multi-Agent Tutorial](https://google.github.io/adk-docs/tutorials/agent-team/)
- [ADK Agents Documentation](https://google.github.io/adk-docs/agents/#agents-working-together-multi-agent-systems)
- [LangChain Multi-Agent Patterns](https://python.langchain.com/docs/use_cases/more/agents/multi_agent/)
- [Best Practices: Single vs Multi-Agent SQL Generation](https://learn.microsoft.com/en-us/dynamics365/guidance/resources/contact-center-multi-agent-architecture-design)

---

## ✅ Conclusión

**Para el estado actual del proyecto (MVP optimizado):**

- ❌ **NO implementar multi-agent** (over-engineering, costos duplicados, latencia aumentada)
- ✅ **Mantener arquitectura actual** (ya optimizada, simple, eficiente)
- ✅ **Documentar arquitectura evolutiva** para futuras expansiones
- ✅ **Considerar híbrido con LangChain** si el sistema crece significativamente

**El sistema actual es la solución correcta para el problema actual.**

---

## 📊 Diagramas de Arquitectura

### Diagrama 1: Arquitectura Actual (MVP Optimizado)

```mermaid
graph TB
    subgraph "Usuario"
        USER[👤 Usuario]
    end
    
    subgraph "CLI Layer"
        CLI[CLI Interface<br/>src/cli.py]
    end
    
    subgraph "Agent Layer - Single Agent"
        AGENT[SQL Agent<br/>create_sql_agent<br/>LangChain Agent]
        AGENT -->|Model Selection| MODEL_SELECT{Clasificación<br/>Simple/Complex}
        MODEL_SELECT -->|Simple| MINI[gpt-4o-mini<br/>💰 $0.15/1M tokens]
        MODEL_SELECT -->|Complex| FULL[gpt-4o<br/>💰 $2.50/1M tokens]
    end
    
    subgraph "Optimization Layer"
        CACHE_CHECK{Cache Check}
        CACHE_CHECK -->|Hit| SQL_CACHE[SQL Cache<br/>Hash-based]
        CACHE_CHECK -->|Hit| SEMANTIC_CACHE[Semantic Cache<br/>Embeddings]
        CACHE_CHECK -->|Miss| LLM_CALL[LLM Call]
    end
    
    subgraph "Processing Layer"
        PROMPT[System Prompt<br/>+ Schema Compact<br/>+ Few-shot Examples]
        SQL_GEN[SQL Generation]
        VALIDATOR[SQL Validator<br/>Whitelist Check]
        ERROR_RECOVERY[Error Recovery<br/>LLM-based]
    end
    
    subgraph "Database Layer"
        ENGINE[SQLAlchemy Engine<br/>Connection Pool]
        POSTGRES[(PostgreSQL<br/>Data Warehouse)]
    end
    
    USER -->|Query| CLI
    CLI -->|Initialize| AGENT
    AGENT --> CACHE_CHECK
    SQL_CACHE -->|Result| CLI
    SEMANTIC_CACHE -->|Result| CLI
    LLM_CALL --> MINI
    LLM_CALL --> FULL
    MINI --> PROMPT
    FULL --> PROMPT
    PROMPT --> SQL_GEN
    SQL_GEN --> VALIDATOR
    VALIDATOR -->|Valid| ENGINE
    VALIDATOR -->|Invalid| ERROR_RECOVERY
    ERROR_RECOVERY --> SQL_GEN
    ENGINE --> POSTGRES
    POSTGRES -->|Results| ENGINE
    ENGINE -->|Results| AGENT
    AGENT -->|Response| CLI
    CLI -->|Formatted| USER
    
    style AGENT fill:#e8f5e9,stroke:#1b5e20
    style MINI fill:#fff3e0,stroke:#e65100
    style FULL fill:#fce4ec,stroke:#880e4f
    style CACHE_CHECK fill:#e1f5ff,stroke:#01579b
    style VALIDATOR fill:#ffebee,stroke:#b71c1c
```

### Diagrama 2: Arquitectura Híbrida Propuesta (Futuro)

```mermaid
graph TB
    subgraph "Usuario"
        USER[👤 Usuario]
    end
    
    subgraph "CLI Layer"
        CLI[CLI Interface]
    end
    
    subgraph "Intent Classification (Sin LLM)"
        INTENT_CLASSIFIER[Intent Classifier<br/>Keyword-based<br/>⚡ <1ms]
        INTENT_CLASSIFIER -->|Analytics| ANALYTICS_INTENT[Analytics Intent]
        INTENT_CLASSIFIER -->|Exploration| EXPLORATION_INTENT[Exploration Intent]
        INTENT_CLASSIFIER -->|Reporting| REPORTING_INTENT[Reporting Intent]
        INTENT_CLASSIFIER -->|Ambiguous| ROOT_AGENT[Root Agent<br/>LLM Decision]
    end
    
    subgraph "Specialized Agents"
        ANALYTICS_AGENT[Analytics Agent<br/>gpt-4o-mini<br/>SUM, COUNT, GROUP BY]
        EXPLORATION_AGENT[Exploration Agent<br/>gpt-4o<br/>JOINs, CTEs, Subqueries]
        REPORTING_AGENT[Reporting Agent<br/>gpt-4o<br/>Structured Reports]
    end
    
    subgraph "Shared Components"
        VALIDATOR[SQL Validator<br/>Whitelist]
        CACHE[Shared Cache<br/>SQL + Semantic]
        ERROR_RECOVERY[Error Recovery]
    end
    
    subgraph "Database"
        ENGINE[SQLAlchemy Engine]
        POSTGRES[(PostgreSQL)]
    end
    
    USER --> CLI
    CLI --> INTENT_CLASSIFIER
    ANALYTICS_INTENT --> ANALYTICS_AGENT
    EXPLORATION_INTENT --> EXPLORATION_AGENT
    REPORTING_INTENT --> REPORTING_AGENT
    ROOT_AGENT -->|Delegate| ANALYTICS_AGENT
    ROOT_AGENT -->|Delegate| EXPLORATION_AGENT
    ROOT_AGENT -->|Delegate| REPORTING_AGENT
    
    ANALYTICS_AGENT --> CACHE
    EXPLORATION_AGENT --> CACHE
    REPORTING_AGENT --> CACHE
    
    ANALYTICS_AGENT --> VALIDATOR
    EXPLORATION_AGENT --> VALIDATOR
    REPORTING_AGENT --> VALIDATOR
    
    VALIDATOR --> ERROR_RECOVERY
    VALIDATOR --> ENGINE
    ERROR_RECOVERY --> VALIDATOR
    ENGINE --> POSTGRES
    POSTGRES --> ENGINE
    ENGINE --> ANALYTICS_AGENT
    ENGINE --> EXPLORATION_AGENT
    ENGINE --> REPORTING_AGENT
    
    ANALYTICS_AGENT --> CLI
    EXPLORATION_AGENT --> CLI
    REPORTING_AGENT --> CLI
    CLI --> USER
    
    style INTENT_CLASSIFIER fill:#c8e6c9,stroke:#2e7d32
    style ANALYTICS_AGENT fill:#fff3e0,stroke:#e65100
    style EXPLORATION_AGENT fill:#fce4ec,stroke:#880e4f
    style REPORTING_AGENT fill:#e3f2fd,stroke:#1565c0
    style ROOT_AGENT fill:#f3e5f5,stroke:#4a148c
```

### Diagrama 3: Flujo de Decisión: ¿Cuándo Implementar Multi-Agent?

```mermaid
flowchart TD
    START[¿Evaluar Multi-Agent?] --> VOLUME{Volumen<br/>>1000 queries/día<br/>con especialización?}
    
    VOLUME -->|No| KEEP_CURRENT[✅ Mantener<br/>Arquitectura Actual]
    VOLUME -->|Sí| DIVERSITY{Diversidad<br/>>3 tipos de queries<br/>analytics/exploration/reporting?}
    
    DIVERSITY -->|No| KEEP_CURRENT
    DIVERSITY -->|Sí| PARALLEL{Necesidad de<br/>Paralelización<br/>Real?}
    
    PARALLEL -->|No| KEEP_CURRENT
    PARALLEL -->|Sí| SPECIALIZATION{Beneficios<br/>Especialización<br/>>10% mejora precisión?}
    
    SPECIALIZATION -->|No| KEEP_CURRENT
    SPECIALIZATION -->|Sí| RESOURCES{Recursos<br/>Equipo y tiempo<br/>para mantener?}
    
    RESOURCES -->|No| KEEP_CURRENT
    RESOURCES -->|Sí| IMPLEMENT_HYBRID[✅ Implementar<br/>Arquitectura Híbrida<br/>LangChain]
    
    IMPLEMENT_HYBRID --> PHASE1[Fase 1: Clasificador<br/>de Intención sin LLM]
    PHASE1 --> PHASE2[Fase 2: Sub-Agents<br/>Especializados]
    PHASE2 --> PHASE3[Fase 3: Routing<br/>Inteligente]
    
    KEEP_CURRENT --> OPTIMIZE[Optimizar Sistema Actual<br/>Model Selection<br/>Caching<br/>Error Recovery]
    
    style KEEP_CURRENT fill:#c8e6c9,stroke:#2e7d32
    style IMPLEMENT_HYBRID fill:#fff3e0,stroke:#e65100
    style VOLUME fill:#e1f5ff,stroke:#01579b
    style DIVERSITY fill:#e1f5ff,stroke:#01579b
    style PARALLEL fill:#e1f5ff,stroke:#01579b
    style SPECIALIZATION fill:#e1f5ff,stroke:#01579b
    style RESOURCES fill:#e1f5ff,stroke:#01579b
```

### Diagrama 4: Comparación de Flujos: Actual vs Multi-Agent

```mermaid
sequenceDiagram
    participant U as Usuario
    participant CLI as CLI
    participant A as Agente Actual
    participant LLM as LLM (1 llamada)
    participant V as Validator
    participant DB as PostgreSQL
    
    Note over U,DB: Flujo Actual (Optimizado)
    U->>CLI: Query
    CLI->>A: create_sql_agent()
    A->>A: Cache Check (SQL/Semantic)
    alt Cache Hit
        A-->>CLI: Resultado Cacheado
    else Cache Miss
        A->>A: Model Selection (simple/complex)
        A->>LLM: 1 llamada LLM
        LLM-->>A: SQL Generado
        A->>V: Validar SQL
        V-->>A: SQL Válido
        A->>DB: Ejecutar Query
        DB-->>A: Resultados
        A->>A: Guardar en Cache
        A-->>CLI: Respuesta
    end
    CLI-->>U: Resultado Formateado
    
    Note over U,DB: Flujo Multi-Agent (Hipotético)
    U->>CLI: Query
    CLI->>A: Root Agent
    A->>LLM: Llamada 1: Decidir delegación
    LLM-->>A: Delegar a Sub-Agent X
    A->>A: Sub-Agent X
    A->>LLM: Llamada 2: Generar SQL
    LLM-->>A: SQL Generado
    A->>V: Validar SQL
    V-->>A: SQL Válido
    A->>DB: Ejecutar Query
    DB-->>A: Resultados
    A-->>CLI: Respuesta
    CLI-->>U: Resultado Formateado
    
    Note right of LLM: ⚠️ 2x Costo<br/>⚠️ 2x Latencia
```

### Diagrama 5: Arquitectura Evolutiva - Roadmap

```mermaid
graph LR
    subgraph "Fase 1: MVP Actual ✅"
        A1[Agente Único<br/>LangChain]
        A2[Model Selection<br/>gpt-4o-mini/gpt-4o]
        A3[Caching Multi-nivel]
        A4[Error Recovery]
        A1 --> A2
        A2 --> A3
        A3 --> A4
    end
    
    subgraph "Fase 2: Híbrido (Futuro)"
        B1[Clasificador<br/>Intención<br/>Sin LLM]
        B2[Sub-Agents<br/>Especializados]
        B3[Routing<br/>Inteligente]
        B1 --> B2
        B2 --> B3
    end
    
    subgraph "Fase 3: Multi-Agent Completo (Solo si Justificado)"
        C1[Root Agent<br/>Orquestador]
        C2[Analytics Agent]
        C3[Exploration Agent]
        C4[Reporting Agent]
        C5[Visualization Agent]
        C1 --> C2
        C1 --> C3
        C1 --> C4
        C1 --> C5
    end
    
    A4 -->|Si crece| B1
    B3 -->|Si justificado| C1
    
    style A1 fill:#c8e6c9,stroke:#2e7d32
    style B1 fill:#fff3e0,stroke:#e65100
    style C1 fill:#fce4ec,stroke:#880e4f
```


