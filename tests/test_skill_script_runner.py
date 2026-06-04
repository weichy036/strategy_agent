from __future__ import annotations

from strategy_agent.services.adk_skills import create_quant_backtest_skill_toolset
from strategy_agent.tools.skill_script_runner import run_allowed_skill_script


def test_allowed_skill_script_validates_schema() -> None:
    response = run_allowed_skill_script("validate_schema", {"schema_json": _macd_510300_schema()})

    assert response.ok
    assert response.data
    parsed = response.data["parsed_json"]
    assert parsed["ok"] is True
    assert parsed["data"]["is_complete"] is True


def test_skill_script_runner_rejects_unknown_script() -> None:
    response = run_allowed_skill_script("not_allowed")

    assert response.ok is False
    assert response.error
    assert response.error.code == "script_not_allowed"


def test_skill_script_runner_rejects_unknown_args() -> None:
    response = run_allowed_skill_script("validate_schema", {"schema_file": "/tmp/schema.json"})

    assert response.ok is False
    assert response.error
    assert response.error.code == "invalid_script_args"


def test_skill_toolset_keeps_adk_code_executor_disabled_by_default() -> None:
    toolset = create_quant_backtest_skill_toolset()

    assert toolset._code_executor is None  # noqa: SLF001
    skill = toolset._list_skills()[0]  # noqa: SLF001
    assert skill.frontmatter.metadata["adk_additional_tools"] == ["run_allowed_skill_script"]


def _macd_510300_schema() -> dict:
    return {
        "schema_version": "v1",
        "name": "沪深300ETF MACD",
        "market": "CN",
        "strategy_type": "signal_trading",
        "universe": {"type": "instrument", "symbols": ["510300.SH"]},
        "period": {"frequency": "1d", "start": "20230101", "end": "20241231"},
        "signals": {
            "buy": [
                {
                    "kind": "indicator_event",
                    "indicator": "macd",
                    "operator": "bullish_cross",
                    "params": {"fast": 12, "slow": 26, "signal": 9},
                }
            ],
            "sell": [
                {
                    "kind": "indicator_event",
                    "indicator": "macd",
                    "operator": "bearish_cross",
                    "params": {"fast": 12, "slow": 26, "signal": 9},
                }
            ],
        },
        "execution": {
            "buy_price": "next_open",
            "sell_price": "next_open",
            "trade_timing": "next_bar",
            "rebalance_trigger": "calendar",
        },
    }
