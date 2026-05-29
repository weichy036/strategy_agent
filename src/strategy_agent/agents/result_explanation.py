from __future__ import annotations

from google.adk import Agent

from strategy_agent.schemas.agent_outputs import ResultExplanationOutput
from .llm_model import create_llm_model
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_result_explanation_agent() -> Agent:
    return Agent(
        name="ResultExplanationAgent",
        model=create_llm_model(),
        description="用用户容易理解的语言解释回测结果。",
        instruction=(
            "请面向普通投资者和研究用户解释回测结果。"
            "必须说明收益曲线、主要回撤、策略稳定性和结果局限。"
            "不要给出投资建议，不要暗示未来收益确定。"
            f"{json_contract_instruction(ResultExplanationOutput)}"
        ),
        output_key="result_explanation",
        **output_schema_kwargs(ResultExplanationOutput),
    )
