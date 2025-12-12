"""Aplicación FastAPI y registro de routers."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import __version__
from src.api.routers import health, history, query, schema, stats, validate_sql
from src.utils.logger import logger

API_V1_PREFIX = "/api/v1"

DEFAULT_ALLOWED_ORIGINS = ["http://localhost:3000"]


def _parse_allowed_origins(env_value: str | None) -> list[str]:
    if env_value is None:
        return DEFAULT_ALLOWED_ORIGINS

    raw_value = env_value.strip()
    if not raw_value:
        return DEFAULT_ALLOWED_ORIGINS

    origins = [origin.strip() for origin in raw_value.split(",") if origin.strip()]

    if "*" in origins:
        logger.warning(
            "WEB_ALLOWED_ORIGINS contiene '*'; wildcard deshabilitado. "
            "Usa una lista explícita de origins."
        )
        origins = [origin for origin in origins if origin != "*"]

    return origins or DEFAULT_ALLOWED_ORIGINS


def create_app() -> FastAPI:
    """Crea la app FastAPI y registra routers."""
    load_dotenv()

    app = FastAPI(
        title="LLM Data Warehouse API",
        version=__version__,
    )

    allowed_origins = _parse_allowed_origins(os.getenv("WEB_ALLOWED_ORIGINS"))
    logger.info(f"CORS allow_origins={allowed_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        max_age=600,
    )

    app.include_router(health.router, prefix=API_V1_PREFIX)
    app.include_router(query.router, prefix=API_V1_PREFIX)
    app.include_router(schema.router, prefix=API_V1_PREFIX)
    app.include_router(history.router, prefix=API_V1_PREFIX)
    app.include_router(stats.router, prefix=API_V1_PREFIX)
    app.include_router(validate_sql.router, prefix=API_V1_PREFIX)

    return app


app = create_app()
