from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from google.adk.tools import BaseTool, ToolContext


TRACE_STATE_KEY = "temp:tool_trace_buffer"
ACTIVE_SUBTASK_KEY = "temp:active_subtask"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_trace(tool_context: ToolContext, entry: dict[str, Any]) -> None:
    current = tool_context.state.get(TRACE_STATE_KEY, [])
    if not isinstance(current, list):
        current = []
    tool_context.state[TRACE_STATE_KEY] = [*current, {"timestamp": _timestamp(), **entry}]


def before_tool_trace(tool: BaseTool, args: dict[str, Any], tool_context: ToolContext) -> None:
    tool_context.state[ACTIVE_SUBTASK_KEY] = tool.name
    _append_trace(
        tool_context,
        {
            "event_type": "tool_start",
            "actor": tool.name,
            "status": "running",
            "message": f"准备执行 {tool.name}",
            "args_preview": sorted(args.keys()),
        },
    )


def after_tool_trace(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict[str, Any],
) -> None:
    ok = tool_response.get("ok") if isinstance(tool_response, dict) else None
    status = "success" if ok is True else "error" if ok is False else "done"
    _append_trace(
        tool_context,
        {
            "event_type": "tool_done",
            "actor": tool.name,
            "status": status,
            "message": f"{tool.name} 执行完成",
        },
    )


def on_tool_error_trace(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    error: Exception,
) -> dict[str, Any] | None:
    _append_trace(
        tool_context,
        {
            "event_type": "tool_error",
            "actor": tool.name,
            "status": "error",
            "message": f"{tool.name} 执行异常：{error}",
        },
    )
    return None
