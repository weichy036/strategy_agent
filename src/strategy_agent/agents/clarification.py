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
        description="用简洁的多轮澄清补齐策略定义中真正缺失的信息。",
        instruction=(
            "当策略字段缺失时，只提出简洁、高信息量的澄清问题。"
            "只询问安全执行回测所必需的最少信息。"
            "不要询问可以安全使用项目默认值的字段：period.start、period.end、commission、slippage、buy_price、sell_price，以及普通日频执行时点。"
            "对于 MACD、均线、RSI 等单标的日线指标策略，只要买入和卖出规则已经明确，就不要询问成交价格、执行时点、是否允许当日买卖或仓位上限。"
            "这类策略使用项目默认口径：T 日收盘后确认信号，下一交易日开盘成交；最多持有一笔多头仓位，不加仓、不做空，符合 A 股 T+1 交易规则。"
            "当用户只说“股票”且没有限定更窄股票池时，默认使用中国 A 股全市场，不要询问使用哪个股票池。"
            "如果缺失的只是可默认字段，请设置 needs_clarification=false，并把这些字段放入 defaultable_fields。"
            "只对不可默认字段提问，例如目标标的、买入规则、卖出规则、选股排序规则、持仓数量、持有周期或调仓规则。"
            "每轮最多只问一个面向用户的问题。"
            "一旦信息足够，就停止追问并进入执行。"
            "如果确实需要澄清，next_question 必须是中文用户问题。"
            f"{json_contract_instruction(ClarificationOutput)}"
        ),
        output_key="clarification_result",
        **output_schema_kwargs(ClarificationOutput),
    )
