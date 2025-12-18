# Arquitectura End-to-End Resumida (PlantUML)

Este documento presenta una vista resumida de la arquitectura y el flujo del sistema utilizando PlantUML.

## Diagrama de Flujo (Sequence Diagram)

```plantuml
@startuml
!theme plain
autonumber

actor "Usuario" as User
participant "CLI Interface" as CLI
box "Core del Sistema" #LightBlue
    participant "SQL Agent\n(Orquestador)" as Agent
    participant "SQL Validator\n(Seguridad)" as Validator
end box
participant "PostgreSQL\n(DW)" as DB
participant "OpenAI API" as AI

User -> CLI: Ingresa Pregunta
activate CLI

CLI -> Agent: Inicia Proceso
activate Agent

Agent -> AI: Genera SQL (con Schema)
activate AI
AI --> Agent: SQL Candidate
deactivate AI

Agent -> Validator: Valida SQL
activate Validator
Validator -> Validator: Verifica Comandos Peligrosos
Validator -> Validator: Verifica Tablas/Columnas
Validator --> Agent: SQL Seguro
deactivate Validator

Agent -> DB: Ejecuta SQL
activate DB
DB --> Agent: Resultados
deactivate DB

Agent -> Agent: Interpreta Resultados
Agent -> CLI: Respuesta Final
deactivate Agent

CLI -> User: Muestra Datos/Respuesta
deactivate CLI
@enduml
```

## Diagrama de Componentes (High Level)

```plantuml
@startuml
!theme plain

package "Interfaz" {
  [CLI] as cli
}

package "Lógica de Negocio" {
    [SQL Agent] as agent
    [SQL Validator] as validator
    [Schema Definition] as schema
}

package "Infraestructura & Externos" {
    database "PostgreSQL" as db
    cloud "OpenAI API" as ai
}

cli --> agent : "Consulta NL"
agent <--> ai : "Generación SQL"
agent --> validator : "Validación"
validator ..> schema : "Reglas Permitidas"
agent --> db : "Lectura de Datos"
@enduml
```
