from __future__ import annotations

import json
from typing import Any, Mapping

from google.adk.agents.readonly_context import ReadonlyContext

from strategy_agent.services.agent_state import read_structured_state
from strategy_agent.services.state_keys import AgentStateKeys


def conversation_context_instruction(ctx: ReadonlyContext) -> str:
    state = ctx.state
    context = _state_dict(state, AgentStateKeys.CONVERSATION_CONTEXT, "ConversationContextAgent")
    schema = _state_dict(state, AgentStateKeys.STRATEGY_SCHEMA, "StrategyDesignerAgent")
    result_page = _state_dict(state, AgentStateKeys.RESULT_PAGE, "")

    blocks = [
        "【当前对话上下文】",
        "如果用户本轮是在追问、比较、微调或继续上轮策略，请优先继承这里的历史策略上下文；不要只根据本轮短句重新判断缺字段。",
    ]
    if context:
        blocks.append("本轮上下文解析：")
        blocks.append(_json(context))
    if schema:
        blocks.append("上一轮/当前有效策略 schema：")
        blocks.append(_json(schema))
    if result_page:
        summary = result_page.get("summary") if isinstance(result_page, dict) else None
        if isinstance(summary, dict):
            blocks.append("上一轮结果摘要：")
            blocks.append(_json(summary))
    if len(blocks) == 2:
        blocks.append("当前没有可继承的上一轮策略。")
    return "\n".join(blocks)


def _state_dict(state: Mapping[str, Any], key: str, agent_name: str) -> dict[str, Any] | None:
    return read_structured_state(state, key, agent_name)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


__all__ = ["conversation_context_instruction"]
