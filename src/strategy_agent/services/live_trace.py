from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from typing import Any


_CURRENT_TRACE_QUEUE: ContextVar[asyncio.Queue[dict[str, Any]] | None] = ContextVar(
    "strategy_agent_live_trace_queue",
    default=None,
)


def set_live_trace_queue(queue: asyncio.Queue[dict[str, Any]] | None) -> Token:
    return _CURRENT_TRACE_QUEUE.set(queue)


def reset_live_trace_queue(token: Token) -> None:
    _CURRENT_TRACE_QUEUE.reset(token)


def emit_live_timeline_item(item: dict[str, Any]) -> None:
    queue = _CURRENT_TRACE_QUEUE.get()
    if queue is not None:
        queue.put_nowait({"type": "timeline", "items": [item]})


__all__ = ["emit_live_timeline_item", "reset_live_trace_queue", "set_live_trace_queue"]
