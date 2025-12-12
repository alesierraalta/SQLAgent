"""Endpoints de query."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from fastapi import APIRouter
from fastapi import Query as FastAPIQuery
from fastapi import Request
from fastapi.responses import StreamingResponse

from src.api.models import QueryRequest, QueryResponse
from src.api.services.query_service import run_query, run_query_stream
from src.utils.logger import logger

router = APIRouter(tags=["query"])


def _format_sse(event: str, data: Any) -> bytes:
    try:
        payload = json.dumps(data, ensure_ascii=False)
    except TypeError:
        payload = json.dumps(str(data), ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


@router.post("/query", response_model=QueryResponse)
def query_endpoint(request: QueryRequest) -> QueryResponse:
    """Ejecuta una consulta en lenguaje natural (single-shot)."""
    return run_query(request)


@router.get("/query/stream")
async def query_stream_endpoint(
    request: Request,
    question: str = FastAPIQuery(min_length=1, max_length=2000),
    limit: int | None = FastAPIQuery(default=None, ge=1, le=10_000),
    explain: bool = FastAPIQuery(default=False),
) -> StreamingResponse:
    """Ejecuta una consulta en streaming usando Server-Sent Events (SSE)."""
    loop = asyncio.get_running_loop()
    stop_event = threading.Event()
    events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def stream_callback(chunk_info: dict | None) -> None:
        if stop_event.is_set() or not chunk_info:
            return

        event_type = str(chunk_info.get("type") or "analysis")
        if event_type == "error":
            loop.call_soon_threadsafe(
                events.put_nowait,
                {
                    "event": "error",
                    "data": {
                        "code": "query_error",
                        "message": str(chunk_info.get("content") or "Error en ejecución."),
                    },
                },
            )
            return

        payload = {
            "type": event_type,
            "content": chunk_info.get("content"),
            "sql": chunk_info.get("sql"),
            "complete": chunk_info.get("complete"),
        }
        loop.call_soon_threadsafe(events.put_nowait, {"event": event_type, "data": payload})

    def worker() -> None:
        try:
            response = run_query_stream(
                question=question,
                limit=limit,
                explain=explain,
                stream_callback=stream_callback,
            )
            loop.call_soon_threadsafe(events.put_nowait, {"event": "done", "data": response.model_dump()})
        except Exception as e:
            logger.exception("Error en /query/stream")
            loop.call_soon_threadsafe(
                events.put_nowait,
                {
                    "event": "error",
                    "data": {"code": "stream_exception", "message": str(e)},
                },
            )
        finally:
            loop.call_soon_threadsafe(events.put_nowait, {"event": "__close__", "data": None})

    threading.Thread(target=worker, daemon=True).start()

    async def event_generator():
        yield b": ok\n\n"
        while True:
            if await request.is_disconnected():
                stop_event.set()
                break

            try:
                item = await asyncio.wait_for(events.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield b": ping\n\n"
                continue

            if item.get("event") == "__close__":
                break

            yield _format_sse(str(item.get("event")), item.get("data"))

        stop_event.set()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
