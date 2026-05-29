from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AdkStreamEventType = Literal[
    "message",
    "tool_call",
    "tool_result",
    "state_trace",
    "usage",
    "error",
    "raw",
]


@dataclass
class AgentTurnResult:
    status: str
    assistant_message: str
    data: dict[str, Any]
    tool_calls: list[dict[str, Any]]
    timeline: list[dict[str, Any]]


@dataclass
class AdkStreamEvent:
    type: AdkStreamEventType
    author: str
    payload: dict[str, Any] = field(default_factory=dict)


__all__ = ["AdkStreamEvent", "AdkStreamEventType", "AgentTurnResult"]
