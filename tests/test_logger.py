"""Tests para configuración de logging."""

from src.utils.logger import setup_logger


def test_setup_logger_reuses_existing_handlers():
    log1 = setup_logger(name="test_logger_unique", log_to_file=False)
    assert log1.handlers  # se configuraron handlers

    log2 = setup_logger(name="test_logger_unique", log_to_file=False)
    assert log2 is log1  # reusa mismo logger sin duplicar
