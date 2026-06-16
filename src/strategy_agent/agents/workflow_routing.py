from __future__ import annotations

from typing import Any

from google.adk.events.event import Event
from google.adk.workflow import node

from strategy_agent.services.agent_state import read_structured_state
from strategy_agent.services.state_keys import AgentStateKeys


@node(name="BacktestRouteNode")
def route_after_clarification(ctx: Any) -> Event:
    intent = _state_dict(ctx, AgentStateKeys.INTENT_CLASSIFICATION)
    clarification = _state_dict(ctx, AgentStateKeys.CLARIFICATION_RESULT)
    route = choose_backtest_route(intent=intent, clarification=clarification)
    ctx.state["workflow.route"] = route
    return Event(route=route)


def choose_backtest_route(*, intent: dict[str, Any], clarification: dict[str, Any]) -> str:
    if intent.get("is_backtest_request") is True and not clarification.get("needs_clarification"):
        return "backtest"
    return "answer"


def _state_dict(ctx: Any, key: str) -> dict[str, Any]:
    agent_name = {
        AgentStateKeys.INTENT_CLASSIFICATION: "IntentClassifierAgent",
        AgentStateKeys.CLARIFICATION_RESULT: "ClarificationAgent",
    }.get(key, "")
    return read_structured_state(ctx.state, key, agent_name) or {}


__all__ = ["choose_backtest_route", "route_after_clarification"]
