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
        description="把已澄清的用户意图转换为可执行的 Strategy Schema JSON。",
        instruction=(
            "请根据用户意图和前文上下文生成 Strategy Schema v1 JSON。"
            "假设要明确且尽量少，只输出回测工具能够执行的字段。"
            "MACD、RSI、均线交叉等单标的择时策略使用 strategy_type='signal_trading'。"
            "每月或定期选股并调仓的横截面策略使用 strategy_type='cross_sectional_rotation'。"
            "不要创造其他 strategy_type 取值。"
            "当用户只说“股票”且没有限定更窄股票池时，设置 universe.type='equity_universe'、universe.scope='A股全市场'、universe.symbols=[]。"
            "横截面轮动策略默认使用 portfolio.weight_method='equal'，除非用户明确要求其他加权方式。"
            "横截面排序必须使用可执行字段：总市值 -> total_mv，流通市值 -> circ_mv，成交额 -> amount，换手率 -> turnover_rate，上个月涨幅 -> monthly_return。"
            "当用户说“上个月/上一月/previous month 成交额最大”时，设置 selection.ranking.lookback='previous_month_sum'。"
            "当用户说“上个月/上一月/previous month 涨幅最大”时，设置 selection.ranking.sort_by='monthly_return' 且 lookback='previous_month_return'。"
            "其他情况保持 selection.ranking.lookback='point_in_time'。"
            "MACD 金叉/死叉策略必须使用下面的买入规则："
            "{'kind':'indicator_event','indicator':'macd','operator':'bullish_cross','params':{'fast':12,'slow':26,'signal':9}} "
            "以及下面的卖出规则："
            "{'kind':'indicator_event','indicator':'macd','operator':'bearish_cross','params':{'fast':12,'slow':26,'signal':9}}. "
            "不要用 cross_above、cross_below、crossover、gt、lt 或信号线比较对象来表达 MACD 交叉。"
            f"{json_contract_instruction(StrategySchema)}"
        ),
        output_key="strategy_schema_draft",
        **output_schema_kwargs(StrategySchema),
    )
