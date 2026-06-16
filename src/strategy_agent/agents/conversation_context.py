from __future__ import annotations

from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from strategy_agent.schemas.agent_outputs import ConversationContextOutput

from .context_prompt import conversation_context_instruction
from .llm_model import create_llm_model
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_conversation_context_agent() -> Agent:
    return Agent(
        name="ConversationContextAgent",
        model=create_llm_model(),
        description="判断当前用户输入是新策略、上一轮策略修改、结果追问还是普通问答，并产出可继承的任务上下文。",
        instruction=_instruction,
        output_key="conversation.context",
        **output_schema_kwargs(ConversationContextOutput),
    )


def _instruction(ctx: ReadonlyContext) -> str:
    return (
        "你是量化研究对话的上下文解析 Agent。"
        "你的任务不是执行回测，而是判断当前用户输入与历史上下文的关系。"
        "如果当前用户说“如果改成...”“只买...只”“换成...”“再看一下...”等追问，"
        "并且上一轮有有效策略，请判断为 strategy_revision，并继承上一轮策略中未被用户明确改变的字段。"
        "如果当前用户是在问上一轮结果原因、交易明细、选股列表或风险，请判断为 result_follow_up。"
        "如果当前用户提出一个完整的新策略，请判断为 new_strategy。"
        "不要用代码规则套字段；请基于对话语义和已有策略结构做判断。"
        "rewritten_query 必须是中文完整任务描述，供后续 Agent 直接理解。"
        "如果是 strategy_revision，rewritten_query 必须包含被继承的核心策略、用户本轮修改点和要继续回测/分析的目标。"
        "patch_hints 只填写你确信的修改提示，例如 {'portfolio.position_count': 10, 'selection.ranking.top_n': 10}。"
        f"\n\n{conversation_context_instruction(ctx)}"
        f"\n\n{json_contract_instruction(ConversationContextOutput)}"
    )


__all__ = ["create_conversation_context_agent"]
