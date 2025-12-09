"""Configuración de logging para el sistema."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Directorio de logs
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Nivel de logging desde variables de entorno
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logger(name: str = "llm_dw", log_to_file: bool = True) -> logging.Logger:
    """
    Configura y retorna un logger.

    Args:
        name: Nombre del logger
        log_to_file: Si True, también escribe logs a archivo

    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Evitar duplicar handlers si ya está configurado
    if logger.handlers:
        return logger

    # Formato de logs
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Handler para archivo (opcional)
    if log_to_file:
        file_handler = RotatingFileHandler(
            LOG_DIR / "llm_dw.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Logger global
logger = setup_logger()
