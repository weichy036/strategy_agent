from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from strategy_agent.schemas.tool_contracts import ToolResponse
from strategy_agent.services.agent_state import read_structured_state
from strategy_agent.services.execution_gate import should_execute_backtest
from strategy_agent.services.execution_flow import strategy_execution_steps
from strategy_agent.services.live_trace import emit_live_timeline_item
from strategy_agent.services.state_keys import AgentStateKeys


class StrategyExecutionAgent(BaseAgent):
    """StrategySchema 的确定性执行阶段。"""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if not _should_execute_backtest(ctx):
            return

        schema = _state_dict(ctx, AgentStateKeys.EXECUTABLE_STRATEGY_SCHEMA) or _state_dict(ctx, AgentStateKeys.STRATEGY_SCHEMA_DRAFT)
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
    agent_name_by_key = {
        AgentStateKeys.INTENT_CLASSIFICATION: "IntentClassifierAgent",
        AgentStateKeys.CLARIFICATION_RESULT: "ClarificationAgent",
        AgentStateKeys.STRATEGY_SCHEMA_DRAFT: "StrategyDesignerAgent",
        AgentStateKeys.EXECUTABLE_STRATEGY_SCHEMA: "DataResearchAgent",
        AgentStateKeys.DATA_AVAILABILITY: "DataResearchAgent",
    }
    return read_structured_state(ctx.session.state, key, agent_name_by_key.get(key, ""))


def _should_execute_backtest(ctx: InvocationContext) -> bool:
    intent = _state_dict(ctx, AgentStateKeys.INTENT_CLASSIFICATION)
    clarification = _state_dict(ctx, AgentStateKeys.CLARIFICATION_RESULT)
    data_availability = _state_dict(ctx, AgentStateKeys.DATA_AVAILABILITY)
    return should_execute_backtest(intent, clarification, data_availability)


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
        return {AgentStateKeys.BACKTEST_RESULT: payload.get("data")}
    if name == "compute_metrics" and payload.get("ok"):
        return {AgentStateKeys.METRICS_RESULT: payload.get("data")}
    if name == "assemble_result_page" and payload.get("ok"):
        return {AgentStateKeys.RESULT_PAGE: (payload.get("data") or {}).get("result_page"), "workflow.status": "completed"}
    return {}


def _error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message, "details": {}}, "data": None, "meta": {}}


__all__ = ["StrategyExecutionAgent", "create_strategy_execution_agent"]
