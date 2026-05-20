from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from strategy_agent.schemas.agent_outputs import ClarificationOutput
from strategy_agent.schemas.agent_outputs import IntentClassificationOutput
from strategy_agent.schemas.agent_outputs import ResultExplanationOutput
from strategy_agent.schemas.strategy_schema import StrategySchema


AGENT_OUTPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "IntentClassifierAgent": IntentClassificationOutput,
    "ClarificationAgent": ClarificationOutput,
    "StrategyDesignerAgent": StrategySchema,
    "ResultExplanationAgent": ResultExplanationOutput,
}


@dataclass(frozen=True)
class ParsedAgentOutput:
    agent_name: str
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None


def _extract_json_candidate(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("result", "output", "content", "text"):
            if key in value:
                nested = _extract_json_candidate(value[key])
                if nested is not None:
                    return nested
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def parse_agent_output(agent_name: str, value: Any) -> ParsedAgentOutput | None:
    schema = AGENT_OUTPUT_SCHEMAS.get(agent_name)
    if schema is None:
        return None

    candidate = _extract_json_candidate(value)
    if candidate is None:
        return ParsedAgentOutput(
            agent_name=agent_name,
            ok=False,
            error="未找到可解析的 JSON 输出",
        )

    try:
        parsed = schema.model_validate(candidate)
    except Exception as exc:  # noqa: BLE001
        return ParsedAgentOutput(
            agent_name=agent_name,
            ok=False,
            error=str(exc),
        )

    return ParsedAgentOutput(
        agent_name=agent_name,
        ok=True,
        data=parsed.model_dump(),
    )
