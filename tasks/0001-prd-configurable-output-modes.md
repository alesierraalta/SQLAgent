# Product Requirements Document (PRD): Configurable Output Modes (Simple/Advanced)

## 1. Introduction
The current system provides detailed outputs including analysis, SQL queries, execution plans, and final answers. While valuable for debugging and transparency, this level of detail can be overwhelming for end-users or distracting during routine use. This feature introduces a "Simple Mode" and a granular configuration system for both the CLI and Frontend to control the visibility of these output components.

## 2. Goals
- **Improve Usability:** Allow users to declutter their interface by hiding technical details (SQL, Thinking/Analysis) when not needed.
- **Flexibility:** Provide granular control over which components are displayed (Response, Analysis, Code, Data).
- **Consistency:** Ensure configurations can be set globally (default) and overridden locally (per-query) across both CLI and Web interfaces.

## 3. User Stories
- **As a non-technical user**, I want to toggle "Simple Mode" so that I only see the final answer and data table, without the confusing SQL code or reasoning steps.
- **As a developer**, I want to use a CLI flag (e.g., `--verbose` or `--show-sql`) to temporarily see the generated query for debugging, even if my default setting is "Simple".
- **As a data analyst**, I want to configure the dashboard to always show the SQL query but hide the verbose "Thinking" process, so I can verify the logic without reading a wall of text.

## 4. Functional Requirements

### 4.1. Configuration Model
The system must support a configuration object governing visibility:
```json
{
  "simple_mode": boolean,       // Master toggle. If true, overrides others to defaults (usually minimal)
  "show_thinking": boolean,     // "Analysis" or "Reasoning" steps
  "show_sql": boolean,          // Generated Code/SQL
  "show_data_table": boolean,   // Raw data results
  "show_visualization": boolean // Charts/Graphs
}
```

### 4.2. CLI Implementation
- **Global Config:** Add a command `config set output <component> <value>` to persist preferences.
- **Runtime Flags:** Support flags that override defaults for the current execution:
    - `--simple`: Forces simple mode (only Answer + Data).
    - `--debug` / `--verbose`: Forces all components to show.
    - `--no-analysis`, `--show-sql`: Granular overrides.

### 4.3. Frontend Implementation (Next.js)
- **State Management:** Use a React Context or Store (e.g., Zustand/Redux) to manage the display preferences.
- **UI Controls:**
    - **Global Toggle:** A "Simple Mode" switch prominent in the UI (e.g., top bar or near chat input).
    - **Granular Settings:** A "View Options" dropdown menu allowing users to toggle individual components (Thinking, SQL, etc.).
- **Persistence:** Save these settings in `localStorage` so they persist across reloads.

### 4.4. Backend Adaptations (FastAPI)
- The API should structure the response object to separate these fields clearly.
- *Note:* The backend should ideally still send the data (unless bandwidth is a major concern), and the filtering should happen on the **client-side** (CLI or Web) to allow toggling without re-fetching.

## 5. Non-Goals
- **Role-Based Restrictions:** This feature is for *display preference*, not security. It does not prevent a user from inspecting the network request to see the SQL if they really want to.
- **Server-Side Filtering:** To keep the UI responsive (toggling "Show SQL" shouldn't require an API call), the backend will continue to send full details, and the client will simply hide/render them.

## 6. Technical Considerations
- **Frontend:** Ensure the "Streaming" response handles hidden chunks gracefully (e.g., if "Thinking" is hidden, those chunks are received but not rendered).
- **CLI:** Use a library like `typer` or `click` (already in use) to handle the new complex flags.

## 7. Success Metrics
- **Adoption:** % of users who toggle "Simple Mode" or modify default view settings.
- **User Satisfaction:** Reduction in feedback regarding "too much text" or "cluttered interface".
