from __future__ import annotations

from google.adk import Agent

from strategy_agent.schemas.agent_outputs import IntentClassificationOutput
from .llm_model import create_llm_model
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_intent_classifier_agent() -> Agent:
    return Agent(
        name="IntentClassifierAgent",
        model=create_llm_model(),
        description="Classifies user research intent and identifies required information.",
        instruction=(
            "Classify the user's request into a quant research intent. "
            "Identify whether the request is backtestable now or requires clarification. "
            "Do not fabricate truly missing trading logic, but treat project-default fields as already backtestable. "
            "Never require clarification for period.start, period.end, ordinary daily frequency, commission, slippage, execution timing, currency, or metric wording such as average yearly return. "
            "When the user says 股票 without naming a narrower universe, infer CN all A-share equities as the default universe instead of marking the universe as missing. "
            "Common Chinese instrument names such as 沪深300ETF, 中证500ETF, 创业板ETF, 证券ETF, 红利ETF can be resolved by tools, so do not mark them as missing when the user names them naturally. "
            "Only mark a request not backtestable when the target universe/instrument, buy rule, sell rule, ranking factor, position count, holding period, or rebalance rule is truly absent. "
            f"{json_contract_instruction(IntentClassificationOutput)}"
        ),
        output_key="intent_classification",
        **output_schema_kwargs(IntentClassificationOutput),
    )
