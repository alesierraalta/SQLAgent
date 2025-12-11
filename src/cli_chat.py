"""Chat-first CLI for natural-language to SQL with safety rails."""

import argparse
import ast
import hashlib
import os
import sys
from typing import Any, Iterable, Sequence

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table
from sqlalchemy import text as sa_text
from sqlalchemy.engine import Engine

from src.agents.sql_agent import create_sql_agent, execute_query
from src.schemas.database_schema import (
    get_schema_for_prompt,
    get_schema_for_prompt_compact,
    load_schema,
)
from src.utils.database import get_db_engine
from src.utils.exceptions import DatabaseConnectionError, SQLValidationError
from src.utils.history import load_history, save_query
from src.utils.logger import logger
from src.utils.redis_client import acquire_lock, release_lock
from src.utils.cache import clear_cache
from src.utils.semantic_cache import clear_semantic_cache
from src.validators.sql_validator import SQLValidator


load_dotenv()


def _safe_env_value(name: str, default: str | None = None) -> str:
    raw = os.getenv(name, default or "")
    if not raw:
        return ""
    if "@" in raw and "://" in raw:
        proto, rest = raw.split("://", 1)
        return f"{proto}://***:***@{rest.split('@')[-1]}"
    return raw


class ChatApp:
    def __init__(
        self,
        mode: str = "safe",
        output_format: str = "table",
        limit: int | None = None,
        timeout: int | None = None,
        plain: bool = False,
    ):
        self.console = Console(color_system=None if plain else "auto")
        self.mode = mode
        self.output_format = output_format
        self.limit = limit or int(os.getenv("MAX_QUERY_ROWS", "1000"))
        self.timeout = timeout or int(os.getenv("QUERY_TIMEOUT", "30"))
        self.schema = load_schema()
        self.validator = SQLValidator(self.schema)
        self.engine: Engine = get_db_engine()
        self.agent = create_sql_agent(self.engine, self.schema)
        self.last_prompt: str | None = None
        self.last_result: Any = None
        self.last_sql: str | None = None

    # Entry point
    def run(self) -> None:
        self._print_banner()
        while True:
            try:
                user_input = Prompt.ask("[bold cyan]chat[/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Bye[/yellow]")
                return

            if not user_input:
                continue
            if user_input.startswith("/"):
                if self._handle_command(user_input):
                    return
            else:
                self._handle_prompt(user_input)

    # Commands
    def _handle_command(self, command: str) -> bool:
        parts = command.split()
        name = parts[0].lower()

        if name in ("/help", "/?", "/commands", "/h"):
            self._print_help()
            return False
        if name in ("/exit", "/quit"):
            self.console.print("[green]Closing session[/green]")
            return True
        if name == "/clearcache":
            clear_cache()
            clear_semantic_cache()
            self.console.print("[green]Cache cleared (SQL + semantic)[/green]")
            return False
        if name == "/schema":
            schema_text = get_schema_for_prompt_compact(self.schema) or get_schema_for_prompt(self.schema)
            self.console.print(Panel(schema_text, title="Schema", border_style="cyan"))
            return False
        if name == "/settings":
            self._print_settings()
            return False
        if name == "/set" and len(parts) > 1:
            self._apply_setting(" ".join(parts[1:]))
            return False
        if name == "/history":
            limit = 10
            if len(parts) > 1 and parts[1].isdigit():
                limit = int(parts[1])
            self._print_history(limit)
            return False
        if name == "/retry":
            if self.last_prompt:
                self._handle_prompt(self.last_prompt, is_retry=True)
            else:
                self.console.print("[yellow]No previous prompt[/yellow]")
            return False
        if name == "/clear":
            self.console.clear()
            self._print_banner()
            return False
        if name == "/sql":
            self._handle_manual_sql()
            return False
        if name == "/export" and len(parts) > 1:
            self._export_last(" ".join(parts[1:]))
            return False

        self.console.print(f"[yellow]Unknown command:[/yellow] {command}")
        return False

    # Prompts
    def _handle_prompt(self, prompt: str, is_retry: bool = False) -> None:
        if self.mode == "safe" and not Confirm.ask("Generate and execute SQL now?", default=False):
            self.console.print("[yellow]Skipped[/yellow]")
            return

        enriched_prompt = prompt
        if self.limit:
            enriched_prompt = f"{prompt.strip()} (limita resultados a {self.limit} filas usando LIMIT)"

        self.last_prompt = prompt
        lock_key = f"lock:prompt:{hashlib.md5(prompt.encode('utf-8')).hexdigest()}"
        got_lock = acquire_lock(lock_key, ttl_seconds=30)
        if not got_lock:
            self.console.print("[yellow]Otra ejecución similar está en curso; intenta de nuevo en unos segundos.[/yellow]")
            return
        try:
            result = execute_query(self.agent, enriched_prompt, return_metadata=True, stream=False)
        except SQLValidationError as e:
            self.console.print(f"[red]Validation error:[/red] {e.message}")
            return
        except DatabaseConnectionError as e:
            self.console.print(f"[red]DB error:[/red] {e.message}")
            return
        except Exception as e:
            logger.exception("Unexpected error in chat prompt")
            self.console.print(f"[red]Error:[/red] {e}")
            return
        finally:
            release_lock(lock_key)

        if isinstance(result, dict):
            response = result.get("response")
            sql_generated = result.get("sql_generated")
            self.last_sql = sql_generated
            self.last_result = response
            self._print_metadata(sql_generated, result)
            self._render_response(response)
            save_query(prompt, sql_generated, str(response) if response else None, success=result.get("success", True))
        else:
            self.last_result = result
            self.last_sql = None
            self._render_response(result)
            save_query(prompt, None, str(result), success=True)

        if not is_retry:
            self.console.print("[dim]Use /retry to resend or /export to save last result[/dim]")

    # Manual SQL
    def _handle_manual_sql(self) -> None:
        self.console.print("[cyan]Paste SQL. Finish with an empty line.[/cyan]")
        lines: list[str] = []
        while True:
            try:
                line = Prompt.ask("sql").rstrip()
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[yellow]Cancelled[/yellow]")
                return
            if line == "":
                break
            lines.append(line)
        sql = "\n".join(lines).strip()
        if not sql:
            self.console.print("[yellow]No SQL provided[/yellow]")
            return
        try:
            self.validator.validate_query(sql)
            with self.engine.connect() as conn:
                result = conn.execute(sa_text(sql))
                rows = result.fetchall()
                columns = list(result.keys())
            self.last_sql = sql
            self.last_result = rows
            self._print_metadata(sql, {"sql_generated": sql, "success": True})
            self._render_table(rows, columns)
            save_query(sql, sql, f"{len(rows)} rows", success=True)
        except SQLValidationError as e:
            self.console.print(f"[red]Validation error:[/red] {e.message}")
        except Exception as e:
            logger.exception("Error executing manual SQL")
            self.console.print(f"[red]Execution error:[/red] {e}")

    # Rendering helpers
    def _render_response(self, response: Any) -> None:
        parsed_rows = self._parse_rows(response)
        if parsed_rows:
            rows, columns = parsed_rows
            self._render_table(rows, columns)
            return
        if isinstance(response, str):
            self.console.print(response)
        else:
            self.console.print(str(response))

    def _render_table(self, rows: Sequence[Sequence[Any]], columns: Iterable[str]) -> None:
        cols = list(columns)
        if not rows:
            self.console.print("[yellow]No rows returned[/yellow]")
            return
        table = Table(show_header=True, header_style="bold magenta")
        for col in cols:
            table.add_column(str(col))
        for row in rows:
            formatted = [self._fmt_value(v) for v in row]
            table.add_row(*formatted)
        self.console.print(table)

    def _print_metadata(self, sql: str | None, meta: dict[str, Any]) -> None:
        parts = []
        if sql:
            parts.append(f"SQL: {sql}")
        if meta.get("execution_time") is not None:
            parts.append(f"t={meta['execution_time']:.2f}s")
        if meta.get("tokens_total") is not None:
            parts.append(f"tokens={meta['tokens_total']}")
        if meta.get("cache_hit_type"):
            parts.append(f"cache={meta['cache_hit_type']}")
        if not parts:
            return
        self.console.print(Panel("\n".join(parts), title="Run info", border_style="dim"))

    # Settings and state
    def _print_banner(self) -> None:
        db_url = _safe_env_value("DATABASE_URL", "***")
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.console.print(Panel("Chat CLI ready. Type a question or /help-like commands (/schema, /history, /sql, /exit).",
                                 title="LLM DW Chat", border_style="blue"))
        self.console.print(f"[dim]DB: {db_url} | Model: {model} | Mode: {self.mode} | Limit: {self.limit} | Timeout: {self.timeout}s[/dim]")

    def _print_settings(self) -> None:
        items = [
            f"mode={self.mode}",
            f"format={self.output_format}",
            f"limit={self.limit}",
            f"timeout={self.timeout}",
        ]
        self.console.print("[cyan]" + " | ".join(items) + "[/cyan]")

    def _print_help(self) -> None:
        help_lines = [
            "/schema       - muestra el schema resumido",
            "/settings     - muestra configuraci\u00f3n actual",
            "/set k=v      - cambia ajustes (mode, limit, timeout, format)",
            "/history [n]  - muestra \u00faltimos prompts",
            "/retry        - reenv\u00eda \u00faltimo prompt",
            "/sql          - pega SQL manual para validar/ejecutar",
            "/export path  - guarda el \u00faltimo resultado",
            "/clear        - limpia pantalla",
            "/clearcache   - limpia caches (SQL + sem\u00e1ntico)",
            "/exit         - salir",
        ]
        self.console.print(Panel("\n".join(help_lines), title="Comandos", border_style="cyan"))

    def _apply_setting(self, expr: str) -> None:
        if "=" not in expr:
            self.console.print("[yellow]Use /set key=value[/yellow]")
            return
        key, value = expr.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "mode" and value in ("safe", "power"):
            self.mode = value
        elif key == "limit" and value.isdigit():
            self.limit = int(value)
        elif key == "timeout" and value.isdigit():
            self.timeout = int(value)
        elif key == "format" and value in ("table", "json", "text"):
            self.output_format = value
        else:
            self.console.print(f"[yellow]Unsupported setting:[/yellow] {expr}")
            return
        self._print_settings()

    def _print_history(self, limit: int) -> None:
        entries = load_history(limit=limit)
        if not entries:
            self.console.print("[yellow]No history[/yellow]")
            return
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("When", style="cyan", width=20)
        table.add_column("Prompt", style="white")
        table.add_column("SQL", style="green")
        for idx, entry in enumerate(entries, 1):
            when = entry.get("timestamp", "")[:19]
            prompt = entry.get("question", "") or "-"
            sql = entry.get("sql", "") or "-"
            table.add_row(str(idx), when, prompt, sql[:60] + ("..." if len(sql) > 60 else ""))
        self.console.print(table)

    def _export_last(self, target: str) -> None:
        if self.last_result is None:
            self.console.print("[yellow]No result to export[/yellow]")
            return
        try:
            path = os.path.abspath(target)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(str(self.last_result))
            self.console.print(f"[green]Saved to {path}[/green]")
        except Exception as e:
            self.console.print(f"[red]Export failed:[/red] {e}")

    # Utils
    def _parse_rows(self, response: Any) -> tuple[list[list[Any]], list[str]] | None:
        data = response
        if isinstance(data, list):
            if not data:
                return [], []
            first = data[0]
            if isinstance(first, dict):
                columns = list(first.keys())
                rows = [[row.get(col) for col in columns] for row in data]  # type: ignore
                return rows, columns
            if isinstance(first, (list, tuple)):
                columns = [f"col_{i+1}" for i in range(len(first))]
                return [list(row) for row in data], columns  # type: ignore
        try:
            parsed = ast.literal_eval(str(response))
            if isinstance(parsed, list) and parsed:
                first = parsed[0]
                if isinstance(first, dict):
                    columns = list(first.keys())
                    rows = [[row.get(col) for col in columns] for row in parsed]  # type: ignore
                    return rows, columns
                if isinstance(first, (list, tuple)):
                    columns = [f"col_{i+1}" for i in range(len(first))]
                    return [list(row) for row in parsed], columns
        except Exception:
            return None
        return None

    @staticmethod
    def _fmt_value(value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, float):
            return f"{value:,.2f}"
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat-first CLI for LLM DW")
    parser.add_argument("--mode", choices=["safe", "power"], default=os.getenv("CHAT_MODE", "safe"))
    parser.add_argument("--format", choices=["table", "json", "text"], default="table")
    parser.add_argument("--limit", type=int, default=None, help="Row limit hint for the agent")
    parser.add_argument("--timeout", type=int, default=None, help="Query timeout seconds")
    parser.add_argument("--plain", action="store_true", help="Disable colors")
    args = parser.parse_args()

    try:
        app = ChatApp(
            mode=args.mode,
            output_format=args.format,
            limit=args.limit,
            timeout=args.timeout,
            plain=args.plain,
        )
        app.run()
    except DatabaseConnectionError as e:
        Console().print(f"[red]DB error:[/red] {e.message}")
        sys.exit(1)
    except Exception as e:
        logger.exception("Fatal error starting chat CLI")
        Console().print(f"[red]Fatal error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
