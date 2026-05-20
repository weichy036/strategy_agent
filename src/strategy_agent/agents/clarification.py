from __future__ import annotations

from google.adk import Agent

from strategy_agent.config import settings
from strategy_agent.schemas.agent_outputs import ClarificationOutput
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_clarification_agent() -> Agent:
    return Agent(
        name="ClarificationAgent",
        model=settings.adk_model,
        description="Conducts concise multi-turn clarification to complete strategy definitions.",
        instruction=(
            "Ask concise, high-signal clarification questions when strategy fields are missing. "
            "Ask only the minimum needed to run backtest safely. "
            "When enough information is available, stop asking and move to execution. "
            "If clarification is needed, next_question must be a user-facing Chinese question. "
            f"{json_contract_instruction(ClarificationOutput)}"
        ),
        output_key="clarification_result",
        **output_schema_kwargs(ClarificationOutput),
    )
