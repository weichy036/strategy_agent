from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from strategy_agent.schemas.tool_contracts import ToolResponse
from strategy_agent.services.adk_event_adapter import extract_text_from_content
from strategy_agent.services.execution_gate import should_execute_backtest
from strategy_agent.services.execution_flow import strategy_execution_steps
from strategy_agent.services.live_trace import emit_live_timeline_item
from strategy_agent.services.structured_outputs import parse_agent_output


class StrategyExecutionAgent(BaseAgent):
    """StrategySchema 的确定性执行阶段。"""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if not _should_execute_backtest(ctx):
            return

        schema = _state_dict(ctx, "data.executable_strategy_schema") or _state_dict(ctx, "strategy_schema_draft")
        if not schema:
            return

        for step in strategy_execution_steps(schema, session_id=ctx.session.id):
            yield _run_tool_call(ctx, self.name, step.name, step.args)
            yield _run_tool_result(ctx, self.name, step.name, step.run())


def create_strategy_execution_agent() -> StrategyExecutionAgent:
    return StrategyExecutionAgent(
        name="StrategyExecutionAgent",
        description="执行确定性的策略校验、回测、指标计算和结果组装。",
    )


def _state_dict(ctx: InvocationContext, key: str) -> dict[str, Any] | None:
    value = ctx.session.state.get(key)
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        return value
    return _latest_strategy_schema(ctx)


def _latest_strategy_schema(ctx: InvocationContext) -> dict[str, Any] | None:
    return _latest_agent_data(ctx, "StrategyDesignerAgent")


def _should_execute_backtest(ctx: InvocationContext) -> bool:
    intent = _latest_agent_data(ctx, "IntentClassifierAgent")
    clarification = _latest_agent_data(ctx, "ClarificationAgent")
    data_availability = _latest_agent_data(ctx, "DataResearchAgent")
    return should_execute_backtest(intent, clarification, data_availability)


def _latest_agent_data(ctx: InvocationContext, agent_name: str) -> dict[str, Any] | None:
    for event in reversed(ctx._get_events(current_invocation=True)):  # noqa: SLF001 - ADK exposes no public current-event iterator.
        if event.author != agent_name:
            continue
        parsed = parse_agent_output(agent_name, extract_text_from_content(event.content))
        if parsed and parsed.ok and isinstance(parsed.data, dict):
            return parsed.data
    return None


def _tool_call_event(ctx: InvocationContext, author: str, name: str, args: dict[str, Any]) -> Event:
    return Event(
        invocation_id=ctx.invocation_id,
        author=author,
        branch=ctx.branch,
        content=types.Content(role="model", parts=[types.Part.from_function_call(name=name, args=args)]),
    )


def _tool_result_event(ctx: InvocationContext, author: str, name: str, response: ToolResponse | dict[str, Any]) -> Event:
    payload = response.model_dump() if hasattr(response, "model_dump") else response
    return Event(
        invocation_id=ctx.invocation_id,
        author=author,
        branch=ctx.branch,
        content=types.Content(role="model", parts=[types.Part.from_function_response(name=name, response=payload)]),
        actions=EventActions(state_delta=_state_delta(name, payload)),
    )


def _run_tool_call(ctx: InvocationContext, author: str, name: str, args: dict[str, Any]) -> Event:
    emit_live_timeline_item(_timeline_item("tool_start", name, "running", f"{name} 开始执行"))
    return _tool_call_event(ctx, author, name, args)


def _run_tool_result(ctx: InvocationContext, author: str, name: str, response: ToolResponse | dict[str, Any]) -> Event:
    payload = response.model_dump() if hasattr(response, "model_dump") else response
    ok = payload.get("ok") if isinstance(payload, dict) else None
    status = "success" if ok is True else "error" if ok is False else "done"
    emit_live_timeline_item(_timeline_item("tool_done", name, status, f"{name} 执行完成"))
    return _tool_result_event(ctx, author, name, response)


def _timeline_item(event_type: str, name: str, status: str, message: str) -> dict[str, str]:
    return {
        "event_type": event_type,
        "actor": name,
        "status": status,
        "stage": name,
        "message": message,
    }


def _state_delta(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if name == "validate_strategy_schema":
        return {"strategy.validation": payload.get("data")}
    if name == "run_backtest" and payload.get("ok"):
        return {"backtest.result": payload.get("data")}
    if name == "compute_metrics" and payload.get("ok"):
        return {"metrics.result": payload.get("data")}
    if name == "assemble_result_page" and payload.get("ok"):
        return {"report.result_page": (payload.get("data") or {}).get("result_page"), "workflow.status": "completed"}
    return {}


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message, "details": {}}, "data": None, "meta": {}}


__all__ = ["StrategyExecutionAgent", "create_strategy_execution_agent"]
