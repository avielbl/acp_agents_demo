"""Thread-safe SSE event emitter using ContextVar for per-run isolation."""
from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar
from typing import Any, Callable

_emitter: ContextVar[Callable | None] = ContextVar("_emitter", default=None)


def set_emitter(fn: Callable) -> None:
    _emitter.set(fn)


def emit(event_type: str, data: dict[str, Any]) -> None:
    fn = _emitter.get()
    if fn is not None:
        fn(event_type, data)


def make_threadsafe_emitter(
    run_id: str,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> Callable:
    """Return a thread-safe emit function that pushes SSE-formatted strings into the queue."""

    def _emit(event_type: str, data: dict[str, Any]) -> None:
        payload = {"run_id": run_id, **data}
        sse = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
        asyncio.run_coroutine_threadsafe(queue.put(sse), loop)

    return _emit
