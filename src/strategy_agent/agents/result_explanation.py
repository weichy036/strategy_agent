from __future__ import annotations

from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from strategy_agent.schemas.agent_outputs import ResultExplanationOutput
from .context_prompt import conversation_context_instruction
from .llm_model import create_llm_model
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_result_explanation_agent() -> Agent:
    return Agent(
        name="ResultExplanationAgent",
        model=create_llm_model(),
        description="用用户容易理解的语言解释当前 Agent 结果。",
        instruction=_instruction,
        include_contents="none",
        output_key="result_explanation",
        **output_schema_kwargs(ResultExplanationOutput),
    )


def _instruction(ctx: ReadonlyContext) -> str:
    return (
        "请根据本轮上下文和已有状态生成面向用户的中文回复。"
        "如果 intent.is_backtest_request=false，或本轮是 general_chat/unsupported，"
        "只做自然回应或说明产品能力，不要解释回测结果，不要描述收益曲线、回撤、夏普、正收益或历史表现。"
        "如果没有真实的 result_page 或 backtest 结果，也不要编造任何收益、曲线走势或风险表现。"
        "只有当已有真实回测结果时，才说明收益曲线、主要回撤、策略稳定性和结果局限。"
        "任何情况下都不要给出投资建议，不要暗示未来收益确定。"
        "对于非回测回复，summary_text 写给用户看的自然回答；risk_text、limitations_text、"
        "equity_curve_commentary 可以简短写“暂无回测结果”。"
        f"\n\n{conversation_context_instruction(ctx)}"
        f"\n\n{json_contract_instruction(ResultExplanationOutput)}"
    )
