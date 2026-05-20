from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from google.genai import types

from strategy_agent.app import build_runner
from strategy_agent.services.agent_trace import TRACE_STATE_KEY
from strategy_agent.services.structured_outputs import AGENT_OUTPUT_SCHEMAS
from strategy_agent.services.structured_outputs import parse_agent_output


@dataclass
class AgentTurnResult:
    status: str
    assistant_message: str
    data: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    timeline: list[dict[str, Any]]


def _to_user_content(message: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=message)])


def _extract_text_from_content(content: types.Content | None) -> str:
    if not content or not content.parts:
        return ""
    chunks: list[str] = []
    for part in content.parts:
        if part.text:
            chunks.append(str(part.text))
    return "".join(chunks).strip()


def _plain_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: _plain_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain_payload(item) for item in value]
    return value


def _short_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}..."


def _timeline_entry(
    *,
    event_type: str,
    actor: str,
    status: str,
    message: str,
    stage: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "actor": actor,
        "status": status,
        "stage": stage or actor,
        "message": message,
    }


def _extract_timeline_entries(event: Any) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    author = str(getattr(event, "author", "") or "agent")

    for function_call in event.get_function_calls():
        name = str(function_call.name or "unknown_tool")
        entries.append(
            _timeline_entry(
                event_type="tool_start",
                actor=name,
                status="running",
                message=f"{name} 开始执行",
            )
        )

    for function_response in event.get_function_responses():
        name = str(function_response.name or "unknown_tool")
        payload = _plain_payload(function_response.response)
        ok = payload.get("ok") if isinstance(payload, dict) else None
        status = "success" if ok is True else "error" if ok is False else "done"
        entries.append(
            _timeline_entry(
                event_type="tool_done",
                actor=name,
                status=status,
                message=f"{name} 执行完成",
            )
        )

    text = _extract_text_from_content(event.content)
    if author != "user" and text and not event.get_function_calls() and not event.get_function_responses():
        entries.append(
            _timeline_entry(
                event_type="agent_decision",
                actor=author,
                status="done",
                message=_short_text(text),
            )
        )

    state_delta = getattr(getattr(event, "actions", None), "state_delta", None) or {}
    trace_buffer = state_delta.get(TRACE_STATE_KEY)
    if isinstance(trace_buffer, list):
        for item in trace_buffer:
            if isinstance(item, dict):
                entries.append(
                    {
                        "event_type": item.get("event_type", "trace"),
                        "actor": item.get("actor", author),
                        "status": item.get("status", "done"),
                        "stage": item.get("stage") or item.get("actor", author),
                        "message": item.get("message", ""),
                        "timestamp": item.get("timestamp"),
                    }
                )
    return entries


def _store_parsed_agent_output(
    *,
    result_data: dict[str, Any],
    timeline: list[dict[str, Any]],
    name: str,
    payload: Any,
) -> None:
    parsed = parse_agent_output(name, payload)
    if parsed is None:
        return

    if parsed.ok and parsed.data is not None:
        if name == "IntentClassifierAgent":
            result_data["intent"] = parsed.data
        elif name == "ClarificationAgent":
            result_data["clarification"] = parsed.data
        elif name == "StrategyDesignerAgent":
            result_data["strategy_schema"] = parsed.data
        elif name == "ResultExplanationAgent":
            result_data["explanations"] = parsed.data
        timeline.append(
            _timeline_entry(
                event_type="agent_output_parsed",
                actor=name,
                status="success",
                stage=name,
                message=f"{name} 结构化输出校验通过",
            )
        )
        return

    timeline.append(
        _timeline_entry(
            event_type="agent_output_parse_failed",
            actor=name,
            status="error",
            stage=name,
            message=f"{name} 结构化输出校验失败：{parsed.error}",
        )
    )


class AgentResearchRuntime:
    def __init__(self) -> None:
        self.runner = build_runner()

    async def _collect_events_async(self, *, user_id: str, session_id: str, message: str):
        events = []
        async for event in self.runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=_to_user_content(message),
        ):
            events.append(event)
        return events

    def run_turn(self, *, user_id: str, session_id: str, message: str) -> AgentTurnResult:
        events = asyncio.run(
            self._collect_events_async(user_id=user_id, session_id=session_id, message=message)
        )
        if not events:
            raise RuntimeError(
                "No agent events received. Please check model connectivity and provider configuration."
            )

        assistant_messages: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        timeline: list[dict[str, Any]] = []
        result_data: dict[str, Any] = {}
        status = "assistant_response"

        for event in events:
            timeline.extend(_extract_timeline_entries(event))
            text = _extract_text_from_content(event.content)
            if event.author != "user" and text:
                assistant_messages.append(text)

            for function_response in event.get_function_responses():
                name = str(function_response.name or "")
                payload = _plain_payload(function_response.response)
                tool_calls.append({"name": name, "payload": payload})
                _store_parsed_agent_output(
                    result_data=result_data,
                    timeline=timeline,
                    name=name,
                    payload=payload,
                )
                if not isinstance(payload, dict):
                    continue
                if name == "validate_strategy_schema":
                    result_data["validation"] = payload.get("data")
                    if payload.get("ok") and isinstance(payload.get("data"), dict):
                        is_complete = bool(payload["data"].get("is_complete"))
                        if not is_complete:
                            status = "needs_clarification"
                elif name == "run_backtest" and payload.get("ok"):
                    result_data["backtest"] = payload.get("data")
                elif name == "compute_metrics" and payload.get("ok"):
                    result_data["metrics"] = payload.get("data")
                elif name == "assemble_result_page" and payload.get("ok"):
                    assembled = payload.get("data") or {}
                    result_data["result_page"] = assembled.get("result_page")
                    status = "completed"

            if event.author in AGENT_OUTPUT_SCHEMAS and text:
                _store_parsed_agent_output(
                    result_data=result_data,
                    timeline=timeline,
                    name=str(event.author),
                    payload=text,
                )

        result_page = result_data.get("result_page")
        equity_series = None
        if isinstance(result_page, dict):
            equity_series = (result_page.get("equity_curve") or {}).get("series")
        if status == "completed" and not equity_series:
            status = "blocked_missing_equity_curve"
            timeline.append(
                _timeline_entry(
                    event_type="result_blocked",
                    actor="ResultGate",
                    status="error",
                    stage="result_page",
                    message="结果页缺少收益曲线，不能标记为完成",
                )
            )

        assistant_message = "\n".join([item for item in assistant_messages if item]).strip()
        clarification = result_data.get("clarification")
        if isinstance(clarification, dict) and clarification.get("needs_clarification"):
            status = "needs_clarification"
            if not clarification.get("next_question"):
                clarification["next_question"] = assistant_message or "需要补充关键信息后再执行回测。"
        if status != "completed":
            validation = result_data.get("validation")
            if isinstance(validation, dict) and validation.get("is_complete") is False:
                status = "needs_clarification"
            elif assistant_message and ("？" in assistant_message or "?" in assistant_message):
                status = "needs_clarification"
        if status == "needs_clarification" and "clarification" not in result_data:
            result_data["clarification"] = {
                "next_question": assistant_message or "需要补充关键信息后再执行回测。",
                "must_ask_fields": [],
            }
        return AgentTurnResult(
            status=status,
            assistant_message=assistant_message,
            data=result_data,
            tool_calls=tool_calls,
            timeline=timeline,
        )


_runtime: AgentResearchRuntime | None = None


def get_agent_runtime() -> AgentResearchRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AgentResearchRuntime()
    return _runtime
