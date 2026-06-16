from __future__ import annotations

from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from strategy_agent.schemas.strategy_schema import StrategySchema
from strategy_agent.services.adk_skills import create_quant_backtest_skill_toolset
from .context_prompt import conversation_context_instruction
from .llm_model import create_llm_model
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_strategy_designer_agent() -> Agent:
    return Agent(
        name="StrategyDesignerAgent",
        model=create_llm_model(),
        description="把已澄清的用户意图转换为可执行的 Strategy Schema JSON。",
        instruction=_instruction,
        output_key="strategy_schema_draft",
        tools=[create_quant_backtest_skill_toolset()],
        **output_schema_kwargs(StrategySchema),
    )


def _instruction(ctx: ReadonlyContext) -> str:
    return (
        "请根据用户意图和前文上下文生成 Strategy Schema v1 JSON。"
        "如果本轮上下文解析显示 rewritten_query，请优先基于 rewritten_query 生成。"
        "如果本轮是 strategy_revision，请读取上一轮/当前有效策略 schema，只修改用户本轮明确要求改变的字段，"
        "并输出修改后的完整 Strategy Schema；不要丢失上一轮已有的排序因子、股票池、持有周期、调仓频率、执行口径。"
        "如果上下文给出了 patch_hints，可以把它作为模型理解本轮修改意图的提示，但仍需保证最终 schema 自洽。"
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
        "均线交叉策略必须使用下面的买入规则："
        "{'kind':'indicator_event','indicator':'ma_cross','operator':'bullish_cross','params':{'fast':10,'slow':60}} "
        "以及下面的卖出规则："
        "{'kind':'indicator_event','indicator':'ma_cross','operator':'bearish_cross','params':{'fast':10,'slow':60}}. "
        "如果用户指定 MA5/MA20、MA10/MA60 等参数，请把 fast/slow 改成用户指定的周期。"
        "RSI 阈值策略必须使用 comparison_rule，例如 RSI 低于30买入："
        "{'kind':'comparison_rule','indicator':'rsi','operator':'lt','params':{'period':14},'value':30}；"
        "RSI 高于70卖出："
        "{'kind':'comparison_rule','indicator':'rsi','operator':'gt','params':{'period':14},'value':70}。"
        f"\n\n{conversation_context_instruction(ctx)}"
        f"\n\n{json_contract_instruction(StrategySchema)}"
    )
