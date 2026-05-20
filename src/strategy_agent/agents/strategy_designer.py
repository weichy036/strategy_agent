from __future__ import annotations

from google.adk import Agent

from strategy_agent.config import settings
from strategy_agent.schemas.strategy_schema import StrategySchema
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_strategy_designer_agent() -> Agent:
    return Agent(
        name="StrategyDesignerAgent",
        model=settings.adk_model,
        description="Transforms clarified user intent into Strategy Schema JSON.",
        instruction=(
            "Generate Strategy Schema v1 JSON from user intent and prior context. "
            "Keep assumptions explicit and minimal. "
            "Output schema fields compatible with the backtest tools. "
            f"{json_contract_instruction(StrategySchema)}"
        ),
        output_key="strategy_schema_draft",
        **output_schema_kwargs(StrategySchema),
    )
