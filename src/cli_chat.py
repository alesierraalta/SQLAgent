"""Chat-first CLI for natural-language to SQL with safety rails."""

import argparse
import ast
import hashlib
import os
import sys
from typing import Any, Iterable, Sequence

try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import Completer, Completion
    PT_AVAILABLE = True
except Exception:
    PT_AVAILABLE = False

from dotenv import load_dotenv
from rich.console import Console, Group
from rich.live import Live
from rich.text import Text
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
from src.utils.semantic_cache import clear_semantic_cache, initialize_semantic_cache
from src.utils.config import load_config, save_config, DEFAULT_CONFIG
from src.validators.sql_validator import SQLValidator


load_dotenv()


class CommandCompleter(Completer):
    def __init__(self, commands: list[tuple[str, str]]):
        self.commands = commands

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        # Mostrar todas las opciones si está vacío o solo "/"
        if text == "" or text == "/":
            for cmd, desc in self.commands:
                display = f"{cmd} — {desc}"
                yield Completion(cmd, start_position=-len(text), display=display)
            return

        # Aceptar sin slash inicial para no perder sugerencias al borrar
        needle = text if text.startswith("/") else f"/{text}"
        for cmd, desc in self.commands:
            if cmd.startswith(needle):
                display = f"{cmd} — {desc}"
                yield Completion(cmd, start_position=-len(text), display=display)


def _safe_env_value(name: str, default: str | None = None) -> str:
    raw = os.getenv(name, default or "")
    if not raw:
        return ""
    if "@" in raw and "://" in raw:
        proto, rest = raw.split("://", 1)
        return f"{proto}://***:***@{rest.split('@')[-1]}"
    return raw


class ChatStreamingDisplay:
    def __init__(self, console: Console, config: dict[str, Any]):
        self.console = console
        self.config = config
        self.sql: str | None = None
        self.status: str = "[cyan]Iniciando...[/cyan]"
        self.analysis: str = ""
        self.error: str | None = None
        self.live: Live | None = None

    def start(self) -> None:
        self.live = Live(self._render(), console=self.console, refresh_per_second=4)
        self.live.start()

    def stop(self) -> None:
        if self.live:
            self.live.stop()
            self.live = None

    def update(self, chunk_info: dict) -> None:
        chunk_type = chunk_info.get("type")
        content = chunk_info.get("content", "")

        if chunk_type == "sql":
            self.sql = content
            self.status = "[cyan]Generando SQL...[/cyan]"
        elif chunk_type in ("execution", "data"):
            self.status = "[green]Ejecutando query...[/green]"
        elif chunk_type == "analysis":
            # Only accumulate if we might show it, but usually safer to always accumulate
            # in case the user toggles it (though here config is static for the run).
            if content:
                self.analysis += str(content)
            self.status = "[yellow]Generando análisis...[/yellow]"
        elif chunk_type == "error":
            self.error = str(content)
            self.status = "[red]Error[/red]"

        if self.live:
            self.live.update(self._render())

    def _render(self):
        simple_mode = self.config.get("simple_mode", False)
        show_sql = self.config.get("show_sql", True)
        show_thinking = self.config.get("show_thinking", True)

        items = []

        # SQL Panel: Hide in simple mode or if explicitly disabled
        if not simple_mode and show_sql:
            sql_panel = Panel(
                Syntax(self.sql, "sql", theme="monokai", line_numbers=False) if self.sql else Text("Esperando SQL...", style="dim"),
                title="SQL",
                border_style="cyan",
            )
            items.append(sql_panel)

        # Status Panel: Always show (gives feedback on progress)
        status_panel = Panel(Text(self.status), title="Estado", border_style="blue")
        items.append(status_panel)

        # Analysis Panel: Hide in simple mode or if explicitly disabled
        if not simple_mode and show_thinking:
            analysis_panel = Panel(Text(self.analysis or "…", style="white"), title="Análisis", border_style="yellow")
            items.append(analysis_panel)

        # Error Panel: Always show if error exists
        if self.error:
            error_panel = Panel(Text(self.error, style="red"), title="Error", border_style="red")
            items.append(error_panel)
            
        return Group(*items)


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
        
        # Load configuration
        self.config = load_config()
        
        # Override config with env vars if present (legacy support)
        if os.getenv("ANALYSIS_ENABLED") is not None:
             self.config["show_thinking"] = os.getenv("ANALYSIS_ENABLED", "true").lower() in ("true", "1", "yes", "on")
        
        self.streaming_enabled = os.getenv("CHAT_STREAM", "true").lower() in ("true", "1", "yes", "on")
        
        self.schema = load_schema()
        self.validator = SQLValidator(self.schema)
        self.engine: Engine = get_db_engine()
        self.agent = create_sql_agent(self.engine, self.schema)
        self.last_prompt: str | None = None
        self.last_result: Any = None
        self.last_sql: str | None = None
        self.session_stats = {
            "queries": 0,
            "cache_sql": 0,
            "cache_semantic": 0,
            "cache_none": 0,
            "tokens_total": 0,
            "tokens_input": 0,
            "tokens_output": 0,
        }
        
        self.commands_info: list[tuple[str, str]] = [
            ("/config", "cambiar ajustes interactivos"),
            ("/setup", "alias de config"),
            ("/schema", "muestra el schema resumido"),
            ("/settings", "muestra configuración actual"),
            ("/set", "cambia ajustes (mode, limit, timeout, format)"),
            ("/history", "muestra últimos prompts"),
            ("/retry", "reenvía último prompt"),
            ("/sql", "pegar SQL manual para validar/ejecutar"),
            ("/export", "guarda el último resultado"),
            ("/clear", "limpia pantalla"),
            ("/clearcache", "limpia caches (SQL + semántico)"),
            ("/clearhistory", "limpia historial local"),
            ("/help", "ayuda"),
            ("/exit", "salir"),
            ("/quit", "salir"),
            ("/?", "ayuda"),
            ("/commands", "ayuda"),
            ("/h", "ayuda"),
        ]
        self.completer = CommandCompleter(self.commands_info) if PT_AVAILABLE else None

    # Entry point
    def run(self) -> None:
        initialize_semantic_cache()  # Preload embeddings to avoid cold-start latency
        self._print_banner()
        try:
            while True:
                try:
                    user_input = self._ask_input().strip()
                except (KeyboardInterrupt, EOFError):
                    self.console.print("\n[yellow]Bye[/yellow]")
                    self._print_session_summary()
                    return

                if not user_input:
                    continue
                if user_input == "/":
                    self._print_help()
                    continue
                if user_input.startswith("/"):
                    if self._handle_command(user_input):
                        break
                else:
                    self._handle_prompt(user_input)
        finally:
            self._print_session_summary()

    # Commands
    def _handle_command(self, command: str) -> bool:
        parts = command.split()
        name = parts[0].lower()

        if name in ("/help", "/?", "/commands", "/h"):
            self._print_help()
            return False
        if name in ("/config", "/setup"):
            self._interactive_config()
            return False
        if name in ("/exit", "/quit"):
            self.console.print("[green]Closing session[/green]")
            return True
        if name == "/clearcache":
            clear_cache()
            clear_semantic_cache()
            self.console.print("[green]Cache cleared (SQL + semantic)[/green]")
            return False
        if name == "/clearhistory":
            from src.utils.history import clear_history
            clear_history()
            self.console.print("[green]History cleared[/green]")
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
            # Decide whether to request analysis based on config
            prefer_analysis = self.config.get("show_thinking", True)
            
            if self.streaming_enabled:
                display = ChatStreamingDisplay(self.console, config=self.config)
                display.start()

                def stream_callback(chunk_info: dict):
                    display.update(chunk_info)

                try:
                    result = execute_query(
                        self.agent,
                        enriched_prompt,
                        return_metadata=True,
                        stream=True,
                        stream_callback=stream_callback,
                        prefer_analysis=prefer_analysis,
                    )
                finally:
                    display.stop()
            else:
                with self.console.status("[cyan]Generando y ejecutando...[/cyan]", spinner="dots"):
                    result = execute_query(
                        self.agent,
                        enriched_prompt,
                        return_metadata=True,
                        stream=False,
                        prefer_analysis=prefer_analysis,
                    )
        except SQLValidationError as e:
            self.console.print(f"[red]Validation error:[/red] {e.message}")
            return
        except DatabaseConnectionError as e:
            self.console.print(f"[red]DB error:[/red] {e.message}")
            return
        except Exception as e:
            logger.exception("Unexpected error in chat prompt")
            msg = str(e)
            if "timeout" in msg.lower():
                self.console.print("[red]Timeout:[/red] la consulta tardó demasiado.")
                self.console.print("[dim]Sugerencia: usa LIMIT más pequeño, añade filtros de fecha o sube QUERY_TIMEOUT.[/dim]")
            else:
                self.console.print(f"[red]Error:[/red] {msg}")
            return
        finally:
            release_lock(lock_key)

        if isinstance(result, dict):
            response = result.get("response")
            sql_generated = result.get("sql_generated")
            self.last_sql = sql_generated
            self.last_result = response
            
            # Print metadata only if not in simple mode or explicitly enabled
            if not self.config.get("simple_mode", False):
                 self._print_metadata(sql_generated, result)
                 
            self._render_response(response)
            save_query(
                prompt,
                sql_generated,
                str(response) if response else None,
                success=result.get("success", True),
                cache_hit_type=result.get("cache_hit_type"),
                model_used=result.get("model_used"),
            )
            self._record_stats(result)
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
        try:
            from src.utils.llm_factory import get_default_model_name, normalize_provider

            provider = normalize_provider()
            model = get_default_model_name(provider) or ""
        except Exception:
            model = os.getenv("OPENAI_MODEL", "")
        self.console.print(Panel("Chat CLI ready. Type a question or /help-like commands (/schema, /history, /sql, /exit).",
                                 title="LLM DW Chat", border_style="blue"))
        
        simple_mode = "ON" if self.config.get("simple_mode") else "OFF"
        analysis = "ON" if self.config.get("show_thinking") else "OFF"
        sql_viz = "ON" if self.config.get("show_sql") else "OFF"
        
        self.console.print(
            f"[dim]DB: {db_url} | Model: {model} | Mode: {self.mode} | "
            f"Limit: {self.limit} | Timeout: {self.timeout}s | "
            f"Simple: {simple_mode} | Analysis: {analysis} | SQL: {sql_viz}[/dim]"
        )

    def _print_settings(self) -> None:
        items = [
            f"mode={self.mode}",
            f"format={self.output_format}",
            f"limit={self.limit}",
            f"timeout={self.timeout}",
            f"simple_mode={self.config.get('simple_mode')}",
            f"show_thinking={self.config.get('show_thinking')}",
            f"show_sql={self.config.get('show_sql')}",
            f"stream={'on' if self.streaming_enabled else 'off'}",
        ]
        self.console.print("[cyan]" + " | ".join(items) + "[/cyan]")

    def _print_help(self) -> None:
        help_lines = [f"{cmd:<12} - {desc}" for cmd, desc in self.commands_info]
        self.console.print(Panel("\n".join(help_lines), title="Comandos", border_style="cyan"))

    def _ask_input(self) -> str:
        if PT_AVAILABLE and self.completer:
            try:
                return pt_prompt("chat> ", completer=self.completer, complete_while_typing=True)
            except Exception:
                return Prompt.ask("[bold cyan]chat[/bold cyan]")
        return Prompt.ask("[bold cyan]chat[/bold cyan]")

    def _record_stats(self, meta: dict[str, Any]) -> None:
        self.session_stats["queries"] += 1
        cache_hit = meta.get("cache_hit_type")
        if cache_hit == "sql":
            self.session_stats["cache_sql"] += 1
        elif cache_hit == "semantic":
            self.session_stats["cache_semantic"] += 1
        else:
            self.session_stats["cache_none"] += 1

        for key in ("tokens_total", "tokens_input", "tokens_output"):
            if meta.get(key) is not None:
                self.session_stats[key] += meta.get(key, 0)

    def _print_session_summary(self) -> None:
        q = self.session_stats["queries"]
        if q == 0:
            return
        lines = [
            f"Queries: {q}",
            f"Cache hits: SQL={self.session_stats['cache_sql']} | Semantic={self.session_stats['cache_semantic']} | None={self.session_stats['cache_none']}",
        ]
        if self.session_stats["tokens_total"]:
            lines.append(
                f"Tokens: total={self.session_stats['tokens_total']} "
                f"(in={self.session_stats['tokens_input']}, out={self.session_stats['tokens_output']})"
            )
        self.console.print(Panel("\n".join(lines), title="Sesión", border_style="blue"))

    def _interactive_config(self) -> None:
        """Cambiar ajustes clave, uno por vez, sin reconfigurar todo."""
        try:
            while True:
                panel = Panel(
                    f"1) mode         : {self.mode}\n"
                    f"2) format       : {self.output_format}\n"
                    f"3) limit        : {self.limit}\n"
                    f"4) timeout      : {self.timeout}s\n"
                    f"5) simple_mode  : {self.config.get('simple_mode')}\n"
                    f"6) show_thinking: {self.config.get('show_thinking')}\n"
                    f"7) show_sql     : {self.config.get('show_sql')}\n"
                    f"8) stream       : {'on' if self.streaming_enabled else 'off'}\n\n"
                    "Elige un número para editar o 'done' para salir.",
                    title="Config actual",
                    border_style="cyan",
                )
                self.console.print(panel)
                choice = Prompt.ask("Selecciona (1-8/done)", choices=["1", "2", "3", "4", "5", "6", "7", "8", "done"], default="done")
                if choice == "done":
                    self.console.print("[green]Configuración actualizada[/green]")
                    self._print_settings()
                    return
                if choice == "1":
                    val = Prompt.ask("mode", choices=["safe", "power"], default=self.mode, show_choices=True)
                    self.mode = val
                elif choice == "2":
                    val = Prompt.ask("format", choices=["table", "json", "text"], default=self.output_format, show_choices=True)
                    self.output_format = val
                elif choice == "3":
                    val = Prompt.ask("limit (filas, entero)", default=str(self.limit))
                    if val.isdigit():
                        self.limit = int(val)
                    else:
                        self.console.print("[yellow]Límite inválido; se mantiene el actual[/yellow]")
                elif choice == "4":
                    val = Prompt.ask("timeout (s)", default=str(self.timeout))
                    if val.isdigit():
                        self.timeout = int(val)
                    else:
                        self.console.print("[yellow]Timeout inválido; se mantiene el actual[/yellow]")
                elif choice == "5":
                    curr = self.config.get("simple_mode", False)
                    val_str = Prompt.ask("simple_mode", choices=["true", "false"], default="true" if curr else "false")
                    new_val = val_str == "true"
                    self.config["simple_mode"] = new_val
                    save_config("simple_mode", new_val)
                elif choice == "6":
                    curr = self.config.get("show_thinking", True)
                    val_str = Prompt.ask("show_thinking", choices=["true", "false"], default="true" if curr else "false")
                    new_val = val_str == "true"
                    self.config["show_thinking"] = new_val
                    save_config("show_thinking", new_val)
                elif choice == "7":
                    curr = self.config.get("show_sql", True)
                    val_str = Prompt.ask("show_sql", choices=["true", "false"], default="true" if curr else "false")
                    new_val = val_str == "true"
                    self.config["show_sql"] = new_val
                    save_config("show_sql", new_val)
                elif choice == "8":
                    val = Prompt.ask("stream", choices=["on", "off"], default="on" if self.streaming_enabled else "off", show_choices=True)
                    self.streaming_enabled = val == "on"
        except (KeyboardInterrupt, EOFError):
            self.console.print("\n[yellow]Configuración cancelada[/yellow]")

    def _apply_setting(self, expr: str) -> None:
        if "=" not in expr:
            self.console.print("[yellow]Use /set key=value[/yellow]")
            return
        key, value = expr.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        
        bool_val = value.lower() in ("on", "true", "1", "yes")
        
        if key == "mode" and value in ("safe", "power"):
            self.mode = value
        elif key == "limit" and value.isdigit():
            self.limit = int(value)
        elif key == "timeout" and value.isdigit():
            self.timeout = int(value)
        elif key == "format" and value in ("table", "json", "text"):
            self.output_format = value
        elif key == "stream":
            self.streaming_enabled = bool_val
        elif key == "simple_mode":
            self.config["simple_mode"] = bool_val
            save_config("simple_mode", bool_val)
        elif key == "show_thinking" or key == "analysis":
            self.config["show_thinking"] = bool_val
            save_config("show_thinking", bool_val)
        elif key == "show_sql":
            self.config["show_sql"] = bool_val
            save_config("show_sql", bool_val)
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
