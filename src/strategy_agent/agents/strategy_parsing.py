from __future__ import annotations

from google.adk import Agent

from strategy_agent.config import settings


def create_strategy_parsing_agent() -> Agent:
    return Agent(
        name="StrategyParsingAgent",
        model=settings.adk_model,
        description="Parses natural-language quant research queries into structured strategy drafts.",
        instruction=(
            "Read a user's quant research question and extract a structured strategy draft. "
            "Identify strategy type, universe, signals or selection logic, rebalance frequency, "
            "and missing fields that may require clarification."
        ),
        output_key="strategy_parsing_result",
    )
