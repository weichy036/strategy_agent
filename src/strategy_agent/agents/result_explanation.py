from __future__ import annotations

from google.adk import Agent

from strategy_agent.config import settings
from strategy_agent.schemas.agent_outputs import ResultExplanationOutput
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_result_explanation_agent() -> Agent:
    return Agent(
        name="ResultExplanationAgent",
        model=settings.adk_model,
        description="Explains backtest results in user-friendly language.",
        instruction=(
            "Explain backtest outcomes for retail and research users. "
            "Always discuss the equity curve, major drawdowns, stability, and limitations. "
            "Do not provide investment advice. "
            f"{json_contract_instruction(ResultExplanationOutput)}"
        ),
        output_key="result_explanation",
        **output_schema_kwargs(ResultExplanationOutput),
    )
