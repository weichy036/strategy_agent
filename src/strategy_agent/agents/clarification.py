from __future__ import annotations

from google.adk import Agent

from strategy_agent.schemas.agent_outputs import ClarificationOutput
from .llm_model import create_llm_model
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_clarification_agent() -> Agent:
    return Agent(
        name="ClarificationAgent",
        model=create_llm_model(),
        description="Conducts concise multi-turn clarification to complete strategy definitions.",
        instruction=(
            "Ask concise, high-signal clarification questions when strategy fields are missing. "
            "Ask only the minimum needed to run backtest safely. "
            "Do not ask for fields that can safely use project defaults: period.start, period.end, "
            "commission, slippage, buy_price, sell_price, and ordinary execution timing. "
            "For single-instrument daily indicator strategies such as MACD, MA, or RSI with both buy and sell rules present, "
            "do not ask about execution price, execution timing, same-day trading, or position limits. "
            "Use the project default: signal is confirmed after the T-day close and executed at the next trading day's open; "
            "the strategy holds at most one long position, does not pyramid, does not short, and is compatible with A-share T+1 rules. "
            "If the user says 股票 without specifying a narrower universe, use CN all A-share equities as the default universe and do not ask which stock pool to use. "
            "If only defaultable fields are missing, set needs_clarification=false and list them "
            "in defaultable_fields. "
            "Only ask about non-defaultable fields such as target instrument, buy rule, sell rule, "
            "selection ranking, position count, or holding/rebalance rule. "
            "Ask at most one user-facing question per turn. "
            "When enough information is available, stop asking and move to execution. "
            "If clarification is needed, next_question must be a user-facing Chinese question. "
            f"{json_contract_instruction(ClarificationOutput)}"
        ),
        output_key="clarification_result",
        **output_schema_kwargs(ClarificationOutput),
    )
