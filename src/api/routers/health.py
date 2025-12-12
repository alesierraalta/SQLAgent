"""Endpoints de healthcheck."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    """Healthcheck básico (no toca la base de datos)."""
    return HealthResponse()

