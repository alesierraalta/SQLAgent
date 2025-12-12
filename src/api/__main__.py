"""Punto de entrada para ejecutar el API como módulo.

Ejemplos:
    python -m src.api
    WEB_API_HOST=127.0.0.1 WEB_API_PORT=8000 python -m src.api
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Inicia el servidor ASGI con Uvicorn."""
    host = os.getenv("WEB_API_HOST", "127.0.0.1")
    try:
        port = int(os.getenv("WEB_API_PORT", "8000"))
    except ValueError:
        port = 8000

    reload_enabled = os.getenv("WEB_API_RELOAD", "false").lower() in ("true", "1", "yes")

    uvicorn.run("src.api.app:app", host=host, port=port, reload=reload_enabled)


if __name__ == "__main__":
    main()

