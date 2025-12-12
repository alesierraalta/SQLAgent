"""Endpoints de historial."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from src.api.models import ClearHistoryResponse, HistoryEntry, HistoryResponse
from src.utils.history import clear_history, load_history

router = APIRouter(tags=["history"])


@router.get("/history", response_model=HistoryResponse)
def history_endpoint(
    limit: int = Query(default=50, ge=1, le=500, description="Máximo de entradas a retornar."),
    offset: int = Query(default=0, ge=0, le=10_000, description="Offset para paginación."),
    days: int | None = Query(default=None, ge=1, le=365, description="Filtrar entradas de los últimos N días."),
) -> HistoryResponse:
    """Retorna historial local (archivo JSON) con paginación básica."""
    entries = load_history(limit=None)

    if days is not None:
        cutoff = datetime.now() - timedelta(days=days)
        filtered = []
        for entry in entries:
            ts_raw = entry.get("timestamp")
            if not ts_raw:
                continue
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                continue
            if ts >= cutoff:
                filtered.append(entry)
        entries = filtered

    total = len(entries)
    sliced = entries[offset : offset + limit]

    items = [HistoryEntry(**entry) for entry in sliced]
    return HistoryResponse(total=total, items=items)


@router.post("/history/clear", response_model=ClearHistoryResponse)
def clear_history_endpoint() -> ClearHistoryResponse:
    """Elimina el historial local."""
    clear_history()
    return ClearHistoryResponse(success=True)
