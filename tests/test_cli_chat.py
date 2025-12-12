"""Unit tests for chat-first CLI helpers (src.cli_chat)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from src.cli_chat import (
    ChatApp,
    ChatStreamingDisplay,
    CommandCompleter,
    PT_AVAILABLE,
    _safe_env_value,
)


class _Doc:
    def __init__(self, text: str):
        self.text_before_cursor = text


@pytest.mark.skipif(not PT_AVAILABLE, reason="prompt_toolkit not available")
def test_command_completer_lists_all_on_slash():
    commands = [("/help", "ayuda"), ("/exit", "salir")]
    completer = CommandCompleter(commands)
    completions = list(completer.get_completions(_Doc("/"), None))
    assert {c.text for c in completions} == {"/help", "/exit"}
    assert any("ayuda" in c.display_text for c in completions)


@pytest.mark.skipif(not PT_AVAILABLE, reason="prompt_toolkit not available")
def test_command_completer_matches_partial_without_slash():
    commands = [("/help", "ayuda"), ("/history", "historial")]
    completer = CommandCompleter(commands)
    completions = list(completer.get_completions(_Doc("he"), None))
    assert any(c.text == "/help" for c in completions)


def test_safe_env_value_masks_credentials(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    masked = _safe_env_value("DATABASE_URL")
    assert masked.startswith("postgresql://***:***@")
    assert "user:pass" not in masked


def test_chat_streaming_display_updates_state():
    console = Console(record=True)
    display = ChatStreamingDisplay(console, config={"show_thinking": True, "show_sql": True, "simple_mode": False})
    display.update({"type": "sql", "content": "SELECT 1"})
    assert display.sql == "SELECT 1"
    assert "SQL" not in (display.error or "")
    display.update({"type": "analysis", "content": "ok"})
    assert "ok" in display.analysis
    display.update({"type": "execution"})
    assert "Ejecutando" in display.status
    display.update({"type": "error", "content": "boom"})
    assert display.error == "boom"
    assert "Error" in display.status


@patch("src.cli_chat.load_schema")
@patch("src.cli_chat.SQLValidator")
@patch("src.cli_chat.get_db_engine")
@patch("src.cli_chat.create_sql_agent")
@patch("src.cli_chat.load_config") # Patch load_config
def test_chat_app_init_is_light_with_patches(
    mock_load_config,
    mock_create_agent,
    mock_engine,
    mock_validator,
    mock_load_schema,
    sample_schema,
):
    mock_load_config.return_value = {} # Mock empty config
    mock_load_schema.return_value = sample_schema
    mock_validator.return_value = MagicMock()
    mock_engine.return_value = MagicMock()
    mock_create_agent.return_value = MagicMock()

    app = ChatApp(mode="safe", output_format="table", limit=5, timeout=10, plain=True)
    assert app.mode == "safe"
    assert app.limit == 5
    assert app.timeout == 10
    assert any(cmd == "/help" for cmd, _ in app.commands_info)


@patch("src.cli_chat.save_config") # Patch save_config
def test_apply_setting_and_record_stats(mock_save_config):
    app: ChatApp = ChatApp.__new__(ChatApp)
    app.console = Console(record=True)
    app.mode = "safe"
    app.output_format = "table"
    app.limit = 1000
    app.timeout = 30
    app.analysis_enabled = True
    app.streaming_enabled = True
    app.config = {"simple_mode": False, "show_thinking": True, "show_sql": True} # Mock config
    app.session_stats = {
        "queries": 0,
        "cache_sql": 0,
        "cache_semantic": 0,
        "cache_none": 0,
        "tokens_total": 0,
        "tokens_input": 0,
        "tokens_output": 0,
    }

    app._apply_setting("mode=power")
    assert app.mode == "power"
    app._apply_setting("limit=42")
    assert app.limit == 42
    
    # Test new config settings
    app._apply_setting("simple_mode=true")
    assert app.config["simple_mode"] is True
    mock_save_config.assert_called_with("simple_mode", True)

    app._record_stats({"cache_hit_type": "sql", "tokens_total": 3, "tokens_input": 1, "tokens_output": 2})
    assert app.session_stats["queries"] == 1
    assert app.session_stats["cache_sql"] == 1
    assert app.session_stats["tokens_total"] == 3


def test_parse_rows_and_fmt_value():
    app: ChatApp = ChatApp.__new__(ChatApp)
    rows_cols = app._parse_rows([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
    assert rows_cols is not None
    rows, cols = rows_cols
    assert cols == ["a", "b"]
    assert rows == [[1, 2], [3, 4]]

    assert ChatApp._fmt_value(None) == "NULL"
    assert ChatApp._fmt_value(1000) == "1,000"
    assert ChatApp._fmt_value(12.5) == "12.50"


def test_handle_command_routes(monkeypatch: pytest.MonkeyPatch, sample_schema):
    app: ChatApp = ChatApp.__new__(ChatApp)
    app.console = Console(record=True)
    app.commands_info = [("/help", "ayuda")]
    app.schema = sample_schema
    app.last_prompt = None
    app.last_result = None
    app.last_sql = None
    app.mode = "safe"
    app.output_format = "table"
    app.limit = 1000
    app.timeout = 30
    app.analysis_enabled = False
    app.streaming_enabled = False
    app.config = {} # Mock config

    app._print_help = MagicMock()
    app._interactive_config = MagicMock()
    app._print_settings = MagicMock()
    app._print_history = MagicMock()
    app._handle_manual_sql = MagicMock()
    app._export_last = MagicMock()

    # help routes
    assert app._handle_command("/help") is False
    app._print_help.assert_called()

    # config routes
    assert app._handle_command("/config") is False
    app._interactive_config.assert_called()

    # exit routes
    assert app._handle_command("/exit") is True

    # clearcache calls both clearers
    with patch("src.cli_chat.clear_cache") as mock_clear, patch("src.cli_chat.clear_semantic_cache") as mock_clear_sem:
        assert app._handle_command("/clearcache") is False
        mock_clear.assert_called_once()
        mock_clear_sem.assert_called_once()

    # unknown command
    assert app._handle_command("/wat") is False
    output = app.console.export_text()
    assert "Unknown command" in output

