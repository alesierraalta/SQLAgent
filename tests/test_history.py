"""Tests para el módulo de historial."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.history import (
    clear_history,
    get_history_entry,
    load_history,
    save_query,
    HISTORY_FILE,
    MAX_HISTORY_ENTRIES,
    DISABLE_HISTORY,
)


@pytest.fixture
def temp_history_file(tmp_path):
    """Crea un archivo de historial temporal."""
    history_file = tmp_path / "test_history.json"
    with patch("src.utils.history.HISTORY_FILE", history_file):
        yield history_file
        # Limpiar después del test
        if history_file.exists():
            history_file.unlink()


def test_save_query(temp_history_file):
    """Test: Guardar query en historial."""
    with patch("src.utils.history.HISTORY_FILE", temp_history_file):
        save_query("test question", "SELECT * FROM sales", "result", success=True)
        
        assert temp_history_file.exists()
        history = load_history()
        assert len(history) == 1
        assert history[0]["question"] == "test question"
        assert history[0]["sql"] == "SELECT * FROM sales"


def test_load_history(temp_history_file):
    """Test: Cargar historial."""
    with patch("src.utils.history.HISTORY_FILE", temp_history_file):
        # Guardar algunas queries
        save_query("question 1", "SQL 1", "result 1")
        save_query("question 2", "SQL 2", "result 2")
        
        history = load_history()
        assert len(history) == 2
        assert history[0]["question"] == "question 2"  # Más reciente primero


def test_load_history_with_limit(temp_history_file):
    """Test: Cargar historial con límite."""
    with patch("src.utils.history.HISTORY_FILE", temp_history_file):
        # Guardar más queries que el límite
        for i in range(5):
            save_query(f"question {i}", f"SQL {i}", f"result {i}")
        
        history = load_history(limit=3)
        assert len(history) == 3


def test_clear_history(temp_history_file):
    """Test: Limpiar historial."""
    with patch("src.utils.history.HISTORY_FILE", temp_history_file):
        save_query("test", "SQL", "result")
        assert temp_history_file.exists()
        
        clear_history()
        assert not temp_history_file.exists()


def test_disable_history_flag(temp_history_file):
    """Test: flag DISABLE_HISTORY evita escribir historial."""
    with patch("src.utils.history.HISTORY_FILE", temp_history_file), patch(
        "src.utils.history.DISABLE_HISTORY", True
    ):
        save_query("test", "SQL", "result")
        history = load_history()
        assert history == []
        assert not temp_history_file.exists()


def test_get_history_entry(temp_history_file):
    """Test: Obtener entrada específica del historial."""
    with patch("src.utils.history.HISTORY_FILE", temp_history_file):
        save_query("question 1", "SQL 1", "result 1")
        save_query("question 2", "SQL 2", "result 2")
        
        entry = get_history_entry(0)
        assert entry is not None
        assert entry["question"] == "question 2"  # Más reciente
        
        entry = get_history_entry(1)
        assert entry is not None
        assert entry["question"] == "question 1"
        
        entry = get_history_entry(10)
        assert entry is None
