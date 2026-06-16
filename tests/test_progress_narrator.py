from __future__ import annotations

from types import SimpleNamespace

from strategy_agent.services.progress_narrator import ProgressNarratorAgent, should_narrate
from strategy_agent.services.agent_runtime import _is_duplicate_narration, _should_skip_narration
from strategy_agent.services.result_collector import StrategyRunResultCollector
from strategy_agent.services.runtime_models import AdkStreamEvent


def _fake_response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_progress_narrator_generates_model_text(monkeypatch) -> None:
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response("我先检查本地数据是否满足这次回测。")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    narrator = ProgressNarratorAgent(completion_fn=fake_completion)
    event = AdkStreamEvent(
        type="tool_result",
        author="StrategyExecutionAgent",
        payload={"name": "run_backtest", "response": {"result": {"ok": True, "data": {"equity_curve": [{"nav": 1.0}]}}}},
    )

    text = narrator.narrate(
        phase="after_action",
        event=event,
        recent_timeline=[
            {"event_type": "narration", "message": "我已经确认了策略条件，可以继续。"},
        ],
    )

    assert text == "我先检查本地数据是否满足这次回测。"
    assert "ProgressNarratorAgent" in captured["messages"][0]["content"]
    assert "执行回测" in captured["messages"][0]["content"]
    assert "叙事上下文" in captured["messages"][0]["content"]
    assert "最近已展示给用户的叙事" in captured["messages"][0]["content"]
    assert "避免连续使用相同开头" in captured["messages"][0]["content"]
    assert "不要展示内部流程判断" in captured["messages"][0]["content"]
    assert "不打断用户" not in captured["messages"][0]["content"]


def test_progress_narrator_does_not_fallback_to_hardcoded_text(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    narrator = ProgressNarratorAgent()

    text = narrator.narrate(
        phase="after_action",
        event=AdkStreamEvent(type="tool_result", author="agent", payload={"name": "run_backtest"}),
    )

    assert text is None


def test_progress_narrator_rejects_placeholder_text(monkeypatch) -> None:
    def fake_completion(**kwargs):
        return _fake_response("回测结果已生成，最大回撤达到Z%，后续可以继续分析。")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    narrator = ProgressNarratorAgent(completion_fn=fake_completion)

    text = narrator.narrate(
        phase="after_action",
        event=AdkStreamEvent(type="tool_result", author="agent", payload={"name": "run_backtest"}),
    )

    assert text is None


def test_should_narrate_runtime_actions() -> None:
    assert should_narrate(
        AdkStreamEvent(type="tool_call", author="agent", payload={"name": "run_backtest"}),
        phase="before_action",
    )
    assert should_narrate(
        AdkStreamEvent(type="tool_call", author="agent", payload={"name": "query_market_data"}),
        phase="before_action",
    )
    assert should_narrate(AdkStreamEvent(type="tool_result", author="agent", payload={"name": "run_backtest"}))
    assert not should_narrate(AdkStreamEvent(type="tool_result", author="agent", payload={"name": "query_market_data"}))
    assert should_narrate(AdkStreamEvent(type="message", author="StrategyDesignerAgent", payload={}))
    assert not should_narrate(AdkStreamEvent(type="message", author="IntentClassifierAgent", payload={}))
    assert not should_narrate(AdkStreamEvent(type="message", author="ResultExplanationAgent", payload={}))
    assert not should_narrate(AdkStreamEvent(type="tool_call", author="agent", payload={"name": "load_skill"}))
    assert not should_narrate(AdkStreamEvent(type="usage", author="StrategyDesignerAgent", payload={}))


def test_runtime_skips_progress_narration_for_general_chat() -> None:
    collector = StrategyRunResultCollector()
    collector.result_data["intent"] = {
        "intent_type": "general_chat",
        "is_backtest_request": False,
    }

    assert _should_skip_narration(
        AdkStreamEvent(type="message", author="ClarificationAgent", payload={}),
        collector,
    )


def test_runtime_skips_duplicate_progress_narration() -> None:
    timeline = [
        {
            "event_type": "narration",
            "message": "我先确认了你的交易条件——阳光电源、日线、MACD金叉买入、死叉卖出，这些关键信息已经足够完整，可以继续整理策略方案了。",
        }
    ]

    assert _is_duplicate_narration(
        "我先确认了你的交易条件——阳光电源、日线、MACD金叉买入、死叉卖出，这些关键信息已经足够完整，可以继续整理策略方案了。",
        timeline,
    )


def test_runtime_keeps_distinct_progress_narration() -> None:
    timeline = [
        {
            "event_type": "narration",
            "message": "我先确认了你的交易条件——阳光电源、日线、MACD金叉买入、死叉卖出，这些关键信息已经足够完整，可以继续整理策略方案了。",
        }
    ]

    assert not _is_duplicate_narration(
        "回测引擎已经跑完，生成了2524个净值点和185笔交易记录，接下来可以计算关键收益指标。",
        timeline,
    )
