from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import asdict
from queue import Empty, Queue
from threading import Lock, Thread
import time
from typing import Any

from google.genai import types

from strategy_agent.app import build_runner
from strategy_agent.config import settings
from strategy_agent.services.adk_event_adapter import adapt_adk_event
from strategy_agent.services.live_trace import reset_live_trace_queue, set_live_trace_queue
from strategy_agent.services.result_collector import StrategyRunResultCollector
from strategy_agent.services.runtime_models import AgentTurnResult


def _to_user_content(message: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=message)])


class AgentResearchRuntime:
    def __init__(self) -> None:
        self.runner = build_runner()
        self._runner_lock = Lock()

    async def _collect_events_async(self, *, user_id: str, session_id: str, message: str):
        events = []
        with self._runner_lock:
            async for event in self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=_to_user_content(message),
            ):
                events.append(event)
        return events

    async def stream_turn(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
    ) -> AsyncIterator[dict]:
        queue = ThreadEventQueue()
        yield {"type": "started", "status": "running"}

        producer = Thread(
            target=self._run_stream_turn_in_thread,
            kwargs={
                "user_id": user_id,
                "session_id": session_id,
                "message": message,
                "queue": queue,
            },
            daemon=True,
        )
        producer.start()

        last_event_at = time.monotonic()
        while True:
            try:
                event = await queue.get(timeout=1)
            except Empty:
                if time.monotonic() - last_event_at > settings.agent_idle_timeout_seconds:
                    yield {
                        "type": "error",
                        "ok": False,
                        "status": "error",
                        "error_code": "agent_idle_timeout",
                        "message": "Agent 等待模型返回超时，请稍后重试。",
                    }
                    return
                continue

            last_event_at = time.monotonic()
            if event.get("type") == "_producer_done":
                return
            yield event

    def _run_stream_turn_in_thread(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
        queue: "ThreadEventQueue",
    ) -> None:
        collector = StrategyRunResultCollector()
        asyncio.run(
            self._run_and_push_events(
                user_id=user_id,
                session_id=session_id,
                message=message,
                collector=collector,
                queue=queue,
            )
        )

    async def _run_and_push_events(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
        collector: StrategyRunResultCollector,
        queue: Any,
    ) -> None:
        saw_event = False
        token = set_live_trace_queue(queue)
        try:
            with self._runner_lock:
                async for event in self.runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=_to_user_content(message),
                ):
                    saw_event = True
                    if _push_adk_event(event, collector, queue):
                        break
            if not saw_event:
                raise RuntimeError(
                    "No agent events received. Please check model connectivity and provider configuration."
                )
            queue.put_nowait({"type": "final", "result": asdict(collector.build())})
        except Exception as exc:  # noqa: BLE001
            queue.put_nowait(
                {
                    "type": "error",
                    "ok": False,
                    "status": "error",
                    "error_code": "agent_stream_failed",
                    "message": str(exc),
                }
            )
        finally:
            reset_live_trace_queue(token)
            queue.put_nowait({"type": "_producer_done"})

    def run_turn(self, *, user_id: str, session_id: str, message: str) -> AgentTurnResult:
        events = asyncio.run(
            self._collect_events_async(user_id=user_id, session_id=session_id, message=message)
        )
        if not events:
            raise RuntimeError(
                "No agent events received. Please check model connectivity and provider configuration."
            )

        collector = StrategyRunResultCollector()
        for event in events:
            for adapted_event in adapt_adk_event(event):
                collector.record(adapted_event)
        return collector.build()


_runtime: AgentResearchRuntime | None = None


class ThreadEventQueue:
    def __init__(self) -> None:
        self._queue: Queue[dict] = Queue()

    def put_nowait(self, item: dict) -> None:
        self._queue.put_nowait(item)

    async def get(self, *, timeout: float) -> dict:
        return await asyncio.to_thread(self._queue.get, True, timeout)


def get_agent_runtime() -> AgentResearchRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AgentResearchRuntime()
    return _runtime


def _push_adk_event(
    event: object,
    collector: StrategyRunResultCollector,
    queue: asyncio.Queue[dict],
) -> bool:
    for adapted_event in adapt_adk_event(event):
        timeline_start = len(collector.timeline)
        collector.record(adapted_event)
        new_items = collector.timeline[timeline_start:]
        if new_items:
            queue.put_nowait({"type": "timeline", "items": new_items})
        if len(collector.tool_calls) >= 20:
            return True
    return False
