# Command Reference

This document provides a comprehensive list of commands for interacting with the CLI, Frontend, and Backend components of the project. Commands are formatted for easy copy-pasting.

## 1. CLI Commands

These commands are used for general project management, testing, and utility functions in the command-line interface.

### General
- **Install Python Dependencies:**
  ```bash
  pip install -r requirements.txt
  ```
- **Run Tests (Full Suite):**
  ```bash
  pytest
  ```
- **Run Tests (with Coverage Report):**
  ```bash
  pytest --cov=src --cov-report=html --cov-report=term-missing
  ```
- **Run Specific Test File:**
  ```bash
  pytest tests/test_your_file.py
  ```
- **Run the CLI Chat Interface:**
  ```bash
  python -m src.cli_chat
  ```
- **Run a specific CLI command (e.g., query, schema, validate-sql):**
  ```bash
  python -m src.cli query "¿cuántas órdenes hay?"
  python -m src.cli schema
  python -m src.cli validate-sql "SELECT * FROM users"
  ```
- **Generate Test Data:**
  ```bash
  python scripts/generate_test_data.py
  ```
- **Test Database Connection:**
  ```bash
  python scripts/test_connection.py
  ```

## 2. Frontend Commands

These commands are used for developing, building, and managing the Next.js frontend application. Navigate to the `frontend/` directory before running these commands.

- **Navigate to Frontend Directory:**
  ```bash
  cd frontend/
  ```
- **Install Node.js Dependencies:**
  ```bash
  npm install
  ```
- **Start Development Server:**
  ```bash
  npm run dev
  ```
- **Build for Production:**
  ```bash
  npm run build
  ```
- **Start Production Server (after build):**
  ```bash
  npm run start
  ```
- **Run Linter:**
  ```bash
  npm run lint
  ```
- **Run Frontend Tests:**
  ```bash
  npm test
  ```
  *(Note: `npm test` typically runs Vitest or Jest based on `package.json` config)*

## 3. Backend Commands

These commands are used for running and managing the FastAPI backend API.

- **Start FastAPI Development Server (from project root):**
  *(Requires `uvicorn` and `fastapi` installed via `pip install -r requirements.txt`)*
  ```bash
  uvicorn src.api.app:app --reload
  ```
- **Start FastAPI Production Server (example with Gunicorn for robustness):**
  *(Requires `gunicorn` to be installed: `pip install gunicorn`)*
  ```bash
  gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.api.app:app
  ```
  *(Note: Adjust `-w` (workers) based on your CPU cores)*

## 4. Docker Commands

These commands are for managing the application using Docker Compose.

- **Build and Run All Services (Backend, Frontend, Database, Redis):**
  ```bash
  docker-compose up --build
  ```
- **Run Services in Detached Mode (Background):**
  ```bash
  docker-compose up -d
  ```
- **Stop All Services:**
  ```bash
  docker-compose down
  ```
- **Stop and Remove Containers, Networks, Volumes, and Images:**
  ```bash
  docker-compose down --volumes --rmi all
  ```
- **View Logs for All Services:**
  ```bash
  docker-compose logs -f
  ```
- **View Logs for a Specific Service (e.g., backend):**
  ```bash
  docker-compose logs -f backend
  ```
