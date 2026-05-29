from __future__ import annotations

from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types

from strategy_agent.services.adk_event_adapter import extract_text_from_content
from strategy_agent.services.data_availability import inspect_strategy_data
from strategy_agent.services.structured_outputs import parse_agent_output


class DataResearchAgent(BaseAgent):
    """在确定性回测前检查本地数据是否就绪。"""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if _skip_data_research(ctx):
            report = _not_required_report("当前请求不需要执行回测数据检查。")
            executable_schema = None
        else:
            schema = _state_dict(ctx, "strategy_schema_draft") or _latest_agent_data(ctx, "StrategyDesignerAgent")
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
    intent = _latest_agent_data(ctx, "IntentClassifierAgent")
    if intent and intent.get("is_backtest_request") is False:
        return True
    clarification = _latest_agent_data(ctx, "ClarificationAgent")
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
        delta["strategy_schema_draft"] = executable_schema
        delta["strategy.schema"] = executable_schema
        delta["data.executable_strategy_schema"] = executable_schema
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
    value = ctx.session.state.get(key)
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return value if isinstance(value, dict) else None


def _latest_agent_data(ctx: InvocationContext, agent_name: str) -> dict[str, Any] | None:
    for event in reversed(ctx._get_events(current_invocation=True)):  # noqa: SLF001 - ADK exposes no public current-event iterator.
        if event.author != agent_name:
            continue
        parsed = parse_agent_output(agent_name, extract_text_from_content(event.content))
        if parsed and parsed.ok and isinstance(parsed.data, dict):
            return parsed.data
    return None


__all__ = ["DataResearchAgent", "apply_schema_patch", "create_data_research_agent"]
