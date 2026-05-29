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
        description="识别用户的量化研究意图，并判断执行回测所需信息是否完整。",
        instruction=(
            "请把用户请求识别为一个量化研究意图。"
            "判断当前请求是否已经可以回测，还是必须先向用户澄清。"
            "不要臆造真正缺失的交易逻辑，但项目默认值可以视为已具备，不应因此阻塞。"
            "不要因为 period.start、period.end、普通日频、手续费、滑点、执行时点、币种，或“每年平均收益”等指标口径措辞而要求澄清。"
            "当用户只说“股票”且没有限定更窄股票池时，默认理解为中国 A 股全市场，不要标记股票池缺失。"
            "沪深300ETF、中证500ETF、创业板ETF、证券ETF、红利ETF 等常见中文标的名称可以由工具解析，用户自然语言提到时不要标记为缺失。"
            "只有在目标标的或股票池、买入规则、卖出规则、排序因子、持仓数量、持有周期、调仓规则真正缺失时，才判断为暂不可回测。"
            f"{json_contract_instruction(IntentClassificationOutput)}"
        ),
        output_key="intent_classification",
        **output_schema_kwargs(IntentClassificationOutput),
    )
