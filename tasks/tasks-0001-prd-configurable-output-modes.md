# Task List: Configurable Output Modes (Simple/Advanced)

## Relevant Files
- `src/cli.py` - Main CLI entry point, needs updates for the new `config` command.
- `src/cli_chat.py` - Handles interactive chat loop and streaming display; core logic for visibility toggles goes here.
- `frontend/app/page.tsx` - Main chat page in the frontend, entry point for UI toggles.
- `frontend/lib/store.ts` (New) - Proposed file for state management (Zustand) for UI settings.
- `frontend/components/ui/view-options.tsx` (New) - Component for the granular "View Options" dropdown.
- `src/utils/config.py` - Logic for loading/saving CLI configuration to a local file.

## Tasks

- [x] 1.0 Core Configuration & Backend Updates
    - [x] 1.1 Create `src/utils/config.py` to handle loading/saving a JSON configuration file (e.g., in `~/.llm-dw/config.json`).
        - Define the schema: `simple_mode`, `show_thinking`, `show_sql`, `show_data`, `show_visualization`.
        - Implement `load_config()` and `save_config(key, value)`.
    - [x] 1.2 Verify `src/api/models.py` and response structures.
        - Ensure the backend response (streaming chunks) clearly distinguishes "analysis" (thinking) from "data" and "sql" so the client can easily filter them. (Existing structure seems adequate, but verify).

- [ ] 2.0 CLI Implementation
    - [ ] 2.1 Add a `config` command group to `src/cli.py`.
        - `llm-dw config set <key> <value>`
        - `llm-dw config get [key]`
        - `llm-dw config list`
    - [ ] 2.2 Update `ChatStreamingDisplay` class in `src/cli_chat.py`.
        - Accept a `config` object or flags in `__init__`.
        - Modify `_render` method to conditionally include/exclude `Panel` components based on visibility settings.
        - Ensure "Simple Mode" forces specific defaults (only Data/Answer).
    - [ ] 2.3 Add runtime flags to `llm-dw query` and interactive chat.
        - Add `--simple`, `--no-analysis`, `--show-sql` flags.
        - Ensure these flags override the persistent configuration loaded from step 1.1.

- [ ] 3.0 Frontend State & UI
    - [ ] 3.1 Setup Client-Side State Management.
        - Install `zustand` (or use React Context) in `frontend/`.
        - Create a store (`useSettingsStore`) to hold `simpleMode`, `showSQL`, `showThinking`, etc., with persistence to `localStorage`.
    - [ ] 3.2 Create "View Options" Component.
        - Create `frontend/components/view-settings.tsx`.
        - Implement a Popover/Dropdown menu with toggle switches for each component.
        - Add a master "Simple Mode" switch that disables/hides the granular options or sets them to a preset.
    - [ ] 3.3 Integrate into Chat Interface (`page.tsx`).
        - Place the "Simple Mode" toggle or Settings icon in the header or near the input.
        - Update the `Chat` or `Message` components to conditionally render the "Thinking" accordion and "SQL" code block based on the store state.
        - Ensure streaming updates don't "flash" hidden content.

- [ ] 4.0 Integration & Testing
    - [ ] 4.1 Test CLI persistence: Set a config, restart CLI, verify setting applies.
    - [ ] 4.2 Test CLI overrides: Set default to "Simple", run with `--debug`, verify full output.
    - [ ] 4.3 Test Frontend persistence: Toggle settings, reload page, verify state is restored.
    - [ ] 4.4 Verify "Simple Mode" UX: Ensure that when enabled, the user sees *only* the final answer/table, and that "Thinking" doesn't clutter the view.
