from __future__ import annotations

from typing import Any

from google.genai import types

from strategy_agent.services.runtime_models import AdkStreamEvent
from strategy_agent.services.state_keys import AgentStateKeys


def adapt_adk_event(event: Any) -> list[AdkStreamEvent]:
    """Convert raw Google ADK events into small Strategy Agent runtime events."""

    adapted: list[AdkStreamEvent] = []
    author = str(getattr(event, "author", "") or "agent")

    error_code = getattr(event, "error_code", None)
    error_message = getattr(event, "error_message", None)
    if error_code or error_message:
        adapted.append(
            AdkStreamEvent(
                type="error",
                author=author,
                payload={"code": error_code, "message": error_message},
            )
        )

    for function_call in event.get_function_calls():
        adapted.append(
            AdkStreamEvent(
                type="tool_call",
                author=author,
                payload={
                    "id": str(function_call.id or ""),
                    "name": str(function_call.name or "unknown_tool"),
                    "args": _plain_payload(function_call.args or {}),
                },
            )
        )

    for function_response in event.get_function_responses():
        adapted.append(
            AdkStreamEvent(
                type="tool_result",
                author=author,
                payload={
                    "id": str(function_response.id or ""),
                    "name": str(function_response.name or "unknown_tool"),
                    "response": _plain_payload(function_response.response),
                },
            )
        )

    text = extract_text_from_content(getattr(event, "content", None))
    if author != "user" and text and not event.get_function_calls() and not event.get_function_responses():
        adapted.append(AdkStreamEvent(type="message", author=author, payload={"text": text}))

    state_delta = getattr(getattr(event, "actions", None), "state_delta", None) or {}
    trace_buffer = state_delta.get(AgentStateKeys.TOOL_TRACE_BUFFER)
    if isinstance(trace_buffer, list):
        for item in trace_buffer:
            if isinstance(item, dict):
                adapted.append(AdkStreamEvent(type="state_trace", author=author, payload=item))

    usage = getattr(event, "usage_metadata", None)
    if usage:
        adapted.append(AdkStreamEvent(type="usage", author=author, payload=_plain_payload(usage)))

    if not adapted:
        adapted.append(AdkStreamEvent(type="raw", author=author, payload={}))
    return adapted


def extract_text_from_content(content: types.Content | None) -> str:
    if not content or not content.parts:
        return ""
    chunks: list[str] = []
    for part in content.parts:
        if part.text:
            chunks.append(str(part.text))
    return "".join(chunks).strip()


def plain_payload(value: Any) -> Any:
    return _plain_payload(value)


def _plain_payload(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {k: _plain_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain_payload(item) for item in value]
    return value


__all__ = ["adapt_adk_event", "extract_text_from_content", "plain_payload"]
