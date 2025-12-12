"""Tests for src.__main__ entry point."""

from __future__ import annotations

import runpy


def test_main_module_runs_cli(monkeypatch):
    import src.cli as cli_module

    called = {"ok": False}

    def fake_cli():
        called["ok"] = True

    monkeypatch.setattr(cli_module, "cli", fake_cli)
    runpy.run_module("src.__main__", run_name="__main__")
    assert called["ok"] is True

