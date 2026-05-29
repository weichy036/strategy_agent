from __future__ import annotations

from google.adk import Agent

from strategy_agent.schemas.strategy_schema import StrategySchema
from .llm_model import create_llm_model
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_strategy_designer_agent() -> Agent:
    return Agent(
        name="StrategyDesignerAgent",
        model=create_llm_model(),
        description="Transforms clarified user intent into Strategy Schema JSON.",
        instruction=(
            "Generate Strategy Schema v1 JSON from user intent and prior context. "
            "Keep assumptions explicit and minimal. "
            "Output schema fields compatible with the backtest tools. "
            "Use strategy_type='signal_trading' for single instrument timing strategies such as MACD, RSI, or moving-average crosses. "
            "Use strategy_type='cross_sectional_rotation' for monthly or periodic stock selection and rebalance strategies. "
            "Do not invent other strategy_type values. "
            "When the user says 股票 without specifying a narrower universe, set universe.type='equity_universe', universe.scope='A股全市场', and universe.symbols=[]. "
            "For cross-sectional rotation, use portfolio.weight_method='equal' unless the user explicitly asks for another weighting method. "
            "For cross-sectional ranking, use executable data fields: total market cap -> total_mv, "
            "free-float market cap -> circ_mv, traded amount -> amount, turnover -> turnover_rate, previous-month price return -> monthly_return. "
            "When the user says 上个月/上一月/previous month成交额最大, set selection.ranking.lookback='previous_month_sum'. "
            "When the user says 上个月/上一月/previous month涨幅最大, set selection.ranking.sort_by='monthly_return' and lookback='previous_month_return'. "
            "Otherwise keep selection.ranking.lookback='point_in_time'. "
            "For MACD golden/death cross, use buy rule "
            "{'kind':'indicator_event','indicator':'macd','operator':'bullish_cross','params':{'fast':12,'slow':26,'signal':9}} "
            "and sell rule "
            "{'kind':'indicator_event','indicator':'macd','operator':'bearish_cross','params':{'fast':12,'slow':26,'signal':9}}. "
            "Do not use cross_above, cross_below, crossover, gt, lt, or signal-line comparison objects for MACD crosses. "
            f"{json_contract_instruction(StrategySchema)}"
        ),
        output_key="strategy_schema_draft",
        **output_schema_kwargs(StrategySchema),
    )
