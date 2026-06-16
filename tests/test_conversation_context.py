from __future__ import annotations

from types import SimpleNamespace

from strategy_agent.agents.context_prompt import conversation_context_instruction
from strategy_agent.services.result_collector import StrategyRunResultCollector
from strategy_agent.services.runtime_models import AdkStreamEvent
from strategy_agent.services.state_keys import AgentStateKeys
from strategy_agent.services.structured_outputs import parse_agent_output


def test_conversation_context_output_is_parsed() -> None:
    payload = {
        "turn_type": "strategy_revision",
        "confidence": 0.91,
        "should_inherit_previous_strategy": True,
        "rewritten_query": "基于上一轮上月跌幅 TOP20 策略，改为每月买入上月跌幅最大的10只股票，继续回测收益。",
        "revision_summary": "把持仓数量从20只改为10只。",
        "base_strategy_summary": "每月买入上月跌幅最大的20只股票，持有一个月。",
        "patch_hints": {
            "selection.ranking.top_n": 10,
            "portfolio.position_count": 10,
        },
        "rationale": "用户使用“如果只买入10只”承接上一轮结果，语义上是修改上一轮策略。",
    }

    parsed = parse_agent_output("ConversationContextAgent", payload)

    assert parsed is not None
    assert parsed.ok
    assert parsed.data["turn_type"] == "strategy_revision"
    assert parsed.data["patch_hints"]["portfolio.position_count"] == 10


def test_collector_stores_conversation_context_state_delta() -> None:
    collector = StrategyRunResultCollector()
    collector.record(
        AdkStreamEvent(
            type="state_delta",
            author="ConversationContextAgent",
            payload={
                AgentStateKeys.CONVERSATION_CONTEXT: {
                    "turn_type": "strategy_revision",
                    "confidence": 0.9,
                    "should_inherit_previous_strategy": True,
                    "rewritten_query": "基于上一轮策略改成 TOP10。",
                    "revision_summary": "TOP20 改 TOP10。",
                    "base_strategy_summary": "上月跌幅 TOP20。",
                    "patch_hints": {"portfolio.position_count": 10},
                    "rationale": "承接上一轮。",
                }
            },
        )
    )

    result = collector.build()

    assert result.data["conversation_context"]["turn_type"] == "strategy_revision"
    assert result.data["conversation_context"]["patch_hints"]["portfolio.position_count"] == 10


def test_context_instruction_includes_previous_strategy_schema() -> None:
    ctx = SimpleNamespace(
        state={
            AgentStateKeys.STRATEGY_SCHEMA: {
                "name": "每月买入上月跌幅最大前20只股票",
                "strategy_type": "cross_sectional_rotation",
                "selection": {
                    "ranking": {
                        "sort_by": "monthly_return",
                        "order": "asc",
                        "top_n": 20,
                        "lookback": "previous_month_return",
                    }
                },
                "portfolio": {
                    "position_count": 20,
                    "rebalance_frequency": "monthly",
                    "weight_method": "equal",
                },
            }
        }
    )

    text = conversation_context_instruction(ctx)  # type: ignore[arg-type]

    assert "上一轮/当前有效策略 schema" in text
    assert "monthly_return" in text
    assert '"top_n": 20' in text
