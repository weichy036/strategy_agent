from __future__ import annotations

from types import SimpleNamespace

from strategy_agent.services.progress_narrator import ProgressNarratorAgent, should_narrate
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
        payload={"name": "query_market_data", "response": {"result": {"ok": True, "data": {"rows": 100}}}},
    )

    text = narrator.narrate(phase="after_action", event=event)

    assert text == "我先检查本地数据是否满足这次回测。"
    assert "ProgressNarratorAgent" in captured["messages"][0]["content"]
    assert "query_market_data" in captured["messages"][0]["content"]


def test_progress_narrator_does_not_fallback_to_hardcoded_text(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    narrator = ProgressNarratorAgent()

    text = narrator.narrate(
        phase="after_action",
        event=AdkStreamEvent(type="tool_result", author="agent", payload={"name": "run_backtest"}),
    )

    assert text is None


def test_should_narrate_runtime_actions() -> None:
    assert not should_narrate(AdkStreamEvent(type="tool_call", author="agent", payload={"name": "run_backtest"}))
    assert should_narrate(AdkStreamEvent(type="tool_result", author="agent", payload={"name": "run_backtest"}))
    assert should_narrate(AdkStreamEvent(type="message", author="StrategyDesignerAgent", payload={}))
    assert not should_narrate(AdkStreamEvent(type="message", author="IntentClassifierAgent", payload={}))
    assert not should_narrate(AdkStreamEvent(type="tool_call", author="agent", payload={"name": "load_skill"}))
    assert not should_narrate(AdkStreamEvent(type="usage", author="StrategyDesignerAgent", payload={}))
