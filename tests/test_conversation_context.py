from __future__ import annotations

from types import SimpleNamespace

from strategy_agent.agents.context_prompt import conversation_context_instruction
from strategy_agent.agents.conversation_context import create_conversation_context_agent
from strategy_agent.agents.intent_classifier import create_intent_classifier_agent
from strategy_agent.agents.clarification import create_clarification_agent
from strategy_agent.agents.result_explanation import _instruction as result_explanation_instruction
from strategy_agent.agents.result_explanation import create_result_explanation_agent
from strategy_agent.agents.strategy_designer import create_strategy_designer_agent
from strategy_agent.agents.workflow_routing import choose_backtest_route, route_after_clarification
from strategy_agent.services.result_collector import StrategyRunResultCollector
from strategy_agent.services.runtime_models import AdkStreamEvent, AgentTurnResult
from strategy_agent.services.state_keys import AgentStateKeys
from strategy_agent.services.strategy_revision import apply_conversation_revision
from strategy_agent.services.structured_outputs import parse_agent_output
from strategy_agent.services.visible_context import build_visible_context


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


def test_context_instruction_prefers_visible_context() -> None:
    ctx = SimpleNamespace(
        state={
            AgentStateKeys.VISIBLE_CONTEXT: {
                "last_user_query": "改成 TOP10",
                "current_strategy_summary": "A股全市场，上月涨幅 TOP20 月度轮动。",
                "current_strategy_schema": {
                    "strategy_type": "cross_sectional_rotation",
                    "selection": {"ranking": {"top_n": 20}},
                },
            },
            AgentStateKeys.STRATEGY_SCHEMA: {
                "selection": {"ranking": {"top_n": 999}},
            },
        }
    )

    text = conversation_context_instruction(ctx)  # type: ignore[arg-type]

    assert "压缩后的可继承上下文" in text
    assert '"top_n": 20' in text
    assert '"top_n": 999' not in text


def test_visible_context_summarizes_without_large_series() -> None:
    result = AgentTurnResult(
        status="completed",
        assistant_message="完成",
        data={
            "conversation_context": {"rewritten_query": "回测 TOP20", "turn_type": "new_strategy"},
            "strategy_schema": {
                "strategy_type": "cross_sectional_rotation",
                "universe": {"scope": "A股全市场"},
                "selection": {"ranking": {"sort_by": "monthly_return", "top_n": 20, "lookback": "previous_month_return"}},
                "portfolio": {"position_count": 20, "rebalance_frequency": "1M"},
            },
            "backtest": {
                "date_range": {"start": "20230101", "end": "20240101"},
                "equity_curve": [{"trade_date": "20230101", "nav": 1.0}],
                "trade_log": [{"symbol": "000001.SZ"}],
            },
            "result_page": {
                "summary": {
                    "strategy_name": "TOP20",
                    "summary_text": "年化收益 -21%",
                    "risk_text": "最大回撤较高",
                },
                "metric_cards": {
                    "return_metrics": {"annualized_return": -0.21},
                    "risk_metrics": {"max_drawdown": 0.74},
                },
                "equity_curve": {
                    "series": [{"trade_date": "20230101", "nav": 1.0}],
                    "artifact": {"uri": "artifact://demo/equity.svg"},
                },
            },
        },
        tool_calls=[],
        timeline=[],
    )

    context = build_visible_context(query="原始问题", result=result)

    assert context["last_goal"] == "回测 TOP20"
    assert context["current_strategy_schema"]["selection"]["ranking"]["top_n"] == 20
    assert context["latest_result_summary"]["return_metrics"]["annualized_return"] == -0.21
    assert context["latest_artifacts"]["equity_curve"]["uri"] == "artifact://demo/equity.svg"
    assert "equity_curve" not in context["latest_result_summary"]
    assert "trade_log" not in context["latest_result_summary"]


def test_llm_agents_use_compact_context_only() -> None:
    agents = [
        create_conversation_context_agent(),
        create_intent_classifier_agent(),
        create_clarification_agent(),
        create_strategy_designer_agent(),
        create_result_explanation_agent(),
    ]

    assert {agent.include_contents for agent in agents} == {"none"}


def test_revision_patch_overrides_stale_market_cap_direction() -> None:
    stale_schema = {
        "schema_version": "v1",
        "name": "每月买入上月市值最大的20只股票",
        "strategy_id": "每月买入上月市值最大的20只股票",
        "market": "CN",
        "strategy_type": "cross_sectional_rotation",
        "universe": {"type": "equity_universe", "symbols": [], "scope": "A股全市场"},
        "period": {"frequency": "1d", "start": None, "end": "latest"},
        "selection": {
            "ranking": {"sort_by": "total_mv", "order": "desc", "top_n": 20, "lookback": "point_in_time"},
            "hold_period": {"type": "fixed", "days": 21},
        },
        "portfolio": {"position_count": 20, "weight_method": "equal", "rebalance_frequency": "monthly"},
        "metadata": {"source_query": "每月买入上月市值最大的10只股票，持有一个月后卖出"},
    }
    context = {
        "turn_type": "strategy_revision",
        "rewritten_query": "继承上一轮每月买入市值最大的20只股票，本轮将排序条件从 total_mv 降序改为升序，即选取市值最小的20只股票。",
        "revision_summary": "将选股排序从总市值降序改为升序，买入市值最小的20只股票。",
        "patch_hints": {
            "selection.ranking.order": "asc",
            "selection.ranking.top_n": 20,
            "portfolio.position_count": 20,
        },
    }

    patched = apply_conversation_revision(stale_schema, context)

    assert patched["selection"]["ranking"]["order"] == "asc"
    assert patched["selection"]["ranking"]["top_n"] == 20
    assert patched["portfolio"]["position_count"] == 20
    assert patched["name"] == "每月买入上月市值最小的20只股票"
    assert patched["strategy_id"] == "每月买入上月市值最小的20只股票"
    assert patched["metadata"]["source_query"] == context["rewritten_query"]


def test_revision_patch_accepts_direction_alias() -> None:
    schema = {
        "strategy_type": "cross_sectional_rotation",
        "selection": {"ranking": {"sort_by": "total_mv", "order": "desc", "top_n": 10}},
        "portfolio": {"position_count": 10},
    }
    context = {
        "turn_type": "strategy_revision",
        "rewritten_query": "改成市值最小的20只。",
        "patch_hints": {"selection.ranking.direction": "ascending"},
    }

    patched = apply_conversation_revision(schema, context)

    assert patched["selection"]["ranking"]["order"] == "asc"
    assert patched["selection"]["ranking"]["top_n"] == 20
    assert patched["portfolio"]["position_count"] == 20


def test_general_chat_routes_directly_to_answer() -> None:
    route = choose_backtest_route(
        intent={
            "intent_type": "general_chat",
            "is_backtest_request": False,
            "is_backtestable_now": False,
        },
        clarification={"needs_clarification": False},
    )

    assert route == "answer"


def test_backtest_request_routes_to_backtest_chain() -> None:
    route = choose_backtest_route(
        intent={
            "intent_type": "cross_sectional_backtest",
            "is_backtest_request": True,
            "is_backtestable_now": True,
        },
        clarification={"needs_clarification": False},
    )

    assert route == "backtest"


def test_route_node_reads_json_string_state_written_by_llm_agents() -> None:
    ctx = SimpleNamespace(
        state={
            AgentStateKeys.INTENT_CLASSIFICATION: (
                '{"intent_type":"single_instrument_backtest","confidence":0.95,'
                '"is_backtest_request":true,"is_backtestable_now":true,'
                '"missing_fields":[],"inferred_fields":{},"reason":"可以回测"}'
            ),
            AgentStateKeys.CLARIFICATION_RESULT: (
                '{"needs_clarification":false,"next_question":null,'
                '"must_ask_fields":[],"defaultable_fields":[],"resolved_fields":{},'
                '"rationale":"信息完整"}'
            ),
        }
    )

    event = route_after_clarification._func(ctx)  # noqa: SLF001

    assert event.actions.route == "backtest"
    assert ctx.state["workflow.route"] == "backtest"


def test_result_explanation_instruction_does_not_force_backtest_for_chat() -> None:
    ctx = SimpleNamespace(
        state={
            AgentStateKeys.CONVERSATION_CONTEXT: {
                "turn_type": "general_chat",
                "confidence": 0.9,
                "should_inherit_previous_strategy": False,
                "rewritten_query": "用户打招呼。",
                "patch_hints": {},
                "rationale": "问候语。",
            }
        }
    )

    text = result_explanation_instruction(ctx)  # type: ignore[arg-type]

    assert "intent.is_backtest_request=false" in text
    assert "不要解释回测结果" in text
    assert "不要描述收益曲线" in text
