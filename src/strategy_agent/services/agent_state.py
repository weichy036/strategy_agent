from __future__ import annotations

from typing import Any, Mapping

from strategy_agent.services.structured_outputs import parse_agent_output


def read_structured_state(state: Mapping[str, Any], key: str, agent_name: str) -> dict[str, Any] | None:
    value = state.get(key)
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = parse_agent_output(agent_name, value)
        if parsed and parsed.ok and isinstance(parsed.data, dict):
            return parsed.data
    return None


__all__ = ["read_structured_state"]
