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
from strategy_agent.services.progress_narrator import ProgressNarratorAgent, should_narrate
from strategy_agent.services.response_slimmer import slim_turn_result
from strategy_agent.services.result_collector import StrategyRunResultCollector, timeline_entry
from strategy_agent.services.runtime_models import AdkStreamEvent, AgentTurnResult


def _to_user_content(message: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=message)])


class AgentResearchRuntime:
    def __init__(self) -> None:
        self.runner = build_runner()
        self.narrator = ProgressNarratorAgent()
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
                    if _push_adk_event(event, collector, queue, narrator=self.narrator):
                        break
            if not saw_event:
                raise RuntimeError(
                    "No agent events received. Please check model connectivity and provider configuration."
                )
            queue.put_nowait({"type": "final", "result": asdict(slim_turn_result(collector.build()))})
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
                _record_adapted_event(
                    adapted_event,
                    collector=collector,
                    narrator=self.narrator,
                    queue=None,
                )
        return slim_turn_result(collector.build())


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
    narrator: ProgressNarratorAgent | None = None,
) -> bool:
    for adapted_event in adapt_adk_event(event):
        _record_adapted_event(adapted_event, collector=collector, narrator=narrator, queue=queue)
        if len(collector.tool_calls) >= 20:
            return True
    return False


def _record_adapted_event(
    event: AdkStreamEvent,
    *,
    collector: StrategyRunResultCollector,
    narrator: ProgressNarratorAgent | None,
    queue: ThreadEventQueue | None,
) -> None:
    timeline_start = len(collector.timeline)
    collector.record(event)
    _push_new_timeline(collector.timeline[timeline_start:], queue)

    if _should_emit_after(event, narrator):
        _record_narration("after_action", event, collector=collector, narrator=narrator, queue=queue)


def _should_emit_after(event: AdkStreamEvent, narrator: ProgressNarratorAgent | None) -> bool:
    return bool(narrator and event.type in {"tool_result", "message"} and should_narrate(event))


def _record_narration(
    phase: str,
    source: AdkStreamEvent,
    *,
    collector: StrategyRunResultCollector,
    narrator: ProgressNarratorAgent | None,
    queue: ThreadEventQueue | None,
) -> None:
    if narrator is None:
        return
    if _narration_count(collector.timeline) >= narrator.max_events:
        return
    text = narrator.narrate(phase=phase, event=source, recent_timeline=collector.timeline)
    if not text:
        return
    event = AdkStreamEvent(
        type="state_trace",
        author="ProgressNarratorAgent",
        payload=timeline_entry(
            event_type="narration",
            actor="ProgressNarratorAgent",
            status="success",
            stage=_source_stage(source),
            message=text,
        ),
    )
    timeline_start = len(collector.timeline)
    collector.record(event)
    _push_new_timeline(collector.timeline[timeline_start:], queue)


def _push_new_timeline(items: list[dict], queue: ThreadEventQueue | None) -> None:
    if items and queue is not None:
        queue.put_nowait({"type": "timeline", "items": items})


def _source_stage(event: AdkStreamEvent) -> str:
    name = event.payload.get("name")
    return str(name or event.author or event.type)


def _narration_count(timeline: list[dict]) -> int:
    return sum(1 for item in timeline if item.get("event_type") == "narration")
