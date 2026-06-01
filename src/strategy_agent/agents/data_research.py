from __future__ import annotations

from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from strategy_agent.services.agent_state import read_structured_state
from strategy_agent.services.data_availability import inspect_strategy_data
from strategy_agent.services.state_keys import AgentStateKeys


class DataResearchAgent(BaseAgent):
    """在确定性回测前检查本地数据是否就绪。"""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if _skip_data_research(ctx):
            report = _not_required_report("当前请求不需要执行回测数据检查。")
            executable_schema = None
        else:
            schema = _state_dict(ctx, AgentStateKeys.STRATEGY_SCHEMA_DRAFT)
            report = inspect_strategy_data(schema) if schema else _not_required_report("未产出可执行策略结构，跳过数据检查。")
            executable_schema = apply_schema_patch(schema, report.schema_patch) if schema else None

        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(role="model", parts=[types.Part.from_text(text=report.model_dump_json())]),
            actions=EventActions(state_delta=_state_delta(report.model_dump(), executable_schema)),
        )


def create_data_research_agent() -> DataResearchAgent:
    return DataResearchAgent(
        name="DataResearchAgent",
        description="检查本地数据可用性，并产出 DataAvailabilityReport。",
    )


def _skip_data_research(ctx: InvocationContext) -> bool:
    intent = _state_dict(ctx, AgentStateKeys.INTENT_CLASSIFICATION)
    if intent and intent.get("is_backtest_request") is False:
        return True
    clarification = _state_dict(ctx, AgentStateKeys.CLARIFICATION_RESULT)
    return bool(clarification and clarification.get("needs_clarification"))


def _not_required_report(rationale: str):
    from strategy_agent.schemas.data_research import DataAvailabilityReport

    return DataAvailabilityReport(is_required=False, is_ready=True, rationale=rationale)


def _state_delta(report: dict[str, Any], executable_schema: dict[str, Any] | None) -> dict[str, Any]:
    delta: dict[str, Any] = {
        "data.availability": report,
        "workflow.data_ready": bool(report.get("can_continue_backtest", report.get("is_ready"))),
    }
    if executable_schema:
        delta[AgentStateKeys.STRATEGY_SCHEMA_DRAFT] = executable_schema
        delta[AgentStateKeys.STRATEGY_SCHEMA] = executable_schema
        delta[AgentStateKeys.EXECUTABLE_STRATEGY_SCHEMA] = executable_schema
    return delta


def apply_schema_patch(schema: dict[str, Any], patch: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(schema)
    for path, value in (patch or {}).items():
        _set_path(out, str(path).split("."), value)
    return out


def _set_path(target: dict[str, Any], parts: list[str], value: Any) -> None:
    if not parts:
        return
    node = target
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _state_dict(ctx: InvocationContext, key: str) -> dict[str, Any] | None:
    agent_name_by_key = {
        AgentStateKeys.INTENT_CLASSIFICATION: "IntentClassifierAgent",
        AgentStateKeys.CLARIFICATION_RESULT: "ClarificationAgent",
        AgentStateKeys.STRATEGY_SCHEMA_DRAFT: "StrategyDesignerAgent",
        AgentStateKeys.DATA_AVAILABILITY: "DataResearchAgent",
    }
    return read_structured_state(ctx.session.state, key, agent_name_by_key.get(key, ""))


__all__ = ["DataResearchAgent", "apply_schema_patch", "create_data_research_agent"]
