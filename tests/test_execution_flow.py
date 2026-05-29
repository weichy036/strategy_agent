from __future__ import annotations

import shutil

from strategy_agent.config import settings
from strategy_agent.domain.signal_backtest import run_signal_backtest
from strategy_agent.services.execution_flow import strategy_execution_steps
from strategy_agent.schemas.strategy_schema import StrategySchema
from strategy_agent.tools.report_assembly import display_strategy_name


def macd_510300_schema() -> dict:
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


def test_macd_execution_flow_success() -> None:
    session_id = "test-macd-execution-flow"
    shutil.rmtree(settings.artifact_root / session_id, ignore_errors=True)

    results = [(step.name, step.run()) for step in strategy_execution_steps(macd_510300_schema(), session_id=session_id)]

    assert [name for name, _ in results] == [
        "validate_strategy_schema",
        "query_market_data",
        "run_backtest",
        "compute_metrics",
        "assemble_result_page",
    ]
    assert all(response.ok for _, response in results)

    backtest = dict(results)["run_backtest"].data
    metrics = dict(results)["compute_metrics"].data
    result_page = dict(results)["assemble_result_page"].data["result_page"]

    assert len(backtest["equity_curve"]) > 100
    assert backtest["summary"]["trade_count"] > 0
    assert metrics["return_metrics"]["annualized_return"] != 0
    assert result_page["equity_curve"]["series"]
    artifact = result_page["equity_curve"]["artifact"]
    assert artifact["url"].startswith(f"/artifacts/{session_id}/")
    assert (settings.artifact_root / session_id / artifact["artifact_id"]).exists()

    shutil.rmtree(settings.artifact_root / session_id, ignore_errors=True)


def test_single_instrument_signal_backtest_does_not_pyramid() -> None:
    backtest = run_signal_backtest(StrategySchema.model_validate(macd_510300_schema()))
    trades = backtest["trade_log"]

    assert trades
    assert trades[0]["side"] == "buy"
    for previous, current in zip(trades, trades[1:], strict=False):
        assert previous["side"] != current["side"]


def test_execution_flow_stops_on_invalid_signal_contract() -> None:
    schema = macd_510300_schema()
    schema["signals"]["buy"][0]["operator"] = "gt"

    results = [(step.name, step.run()) for step in strategy_execution_steps(schema)]

    assert [name for name, _ in results] == ["validate_strategy_schema"]
    validation = results[0][1].data
    assert validation["is_valid"] is False
    assert validation["invalid_fields"] == ["signals.buy[0]"]


def test_monthly_amount_rotation_execution_flow_success() -> None:
    schema = {
        "schema_version": "v1",
        "name": "月度成交额TOP10轮动",
        "market": "CN",
        "strategy_type": "cross_sectional_rotation",
        "universe": {"type": "equity_universe", "symbols": [], "scope": "A股全市场"},
        "period": {"frequency": "1d", "start": "20240101", "end": "20241231"},
        "selection": {
            "ranking": {"sort_by": "amount", "order": "desc", "top_n": 10, "lookback": "previous_month_sum"},
            "hold_period": {"type": "calendar", "frequency": "monthly"},
        },
        "portfolio": {"position_count": 10, "weight_method": "equal", "rebalance_frequency": "monthly"},
        "execution": {"buy_price": "next_open", "sell_price": "next_open", "trade_timing": "next_bar", "rebalance_trigger": "calendar"},
    }

    results = [(step.name, step.run()) for step in strategy_execution_steps(schema, session_id="test-monthly-amount")]

    assert [name for name, _ in results] == [
        "validate_strategy_schema",
        "query_market_data",
        "run_backtest",
        "compute_metrics",
        "assemble_result_page",
    ]
    assert all(response.ok for _, response in results)
    responses = dict(results)
    assert responses["run_backtest"].data["summary"]["trade_count"] > 0
    assert responses["run_backtest"].data["selection_log"]
    snapshots = responses["assemble_result_page"].data["result_page"]["trade_stats"]["selection_snapshots"]
    assert snapshots
    assert snapshots[-1]["symbols"]
    artifact = responses["assemble_result_page"].data["result_page"]["trade_stats"]["selection_artifact"]
    assert artifact["url"].startswith("/artifacts/test-monthly-amount/")
    assert (settings.artifact_root / "test-monthly-amount" / artifact["artifact_id"]).exists()
    trade_stats = responses["assemble_result_page"].data["result_page"]["trade_stats"]
    assert trade_stats["trade_snapshots"]
    assert any(item["realized_profit"] is not None for item in trade_stats["trade_snapshots"])
    assert any(item["cumulative_profit"] is not None for item in trade_stats["trade_snapshots"])
    trade_artifact = trade_stats["trade_artifact"]
    assert trade_artifact["url"].startswith("/artifacts/test-monthly-amount/")
    assert (settings.artifact_root / "test-monthly-amount" / trade_artifact["artifact_id"]).exists()


def test_previous_month_return_rotation_execution_flow_success() -> None:
    schema = {
        "schema_version": "v1",
        "market": "CN",
        "strategy_type": "cross_sectional_rotation",
        "universe": {"type": "equity_universe", "symbols": [], "scope": "A股全市场"},
        "period": {"frequency": "1d", "start": "20240101", "end": "20241231"},
        "selection": {
            "ranking": {"sort_by": "monthly_return", "order": "desc", "top_n": 5, "lookback": "previous_month_return"},
            "hold_period": {"type": "calendar", "frequency": "monthly"},
        },
        "portfolio": {"position_count": 5, "weight_method": "equal", "rebalance_frequency": "monthly"},
        "execution": {"buy_price": "next_open", "sell_price": "next_open", "trade_timing": "next_bar", "rebalance_trigger": "calendar"},
    }

    results = [(step.name, step.run()) for step in strategy_execution_steps(schema, session_id="test-monthly-return")]

    assert [name for name, _ in results] == [
        "validate_strategy_schema",
        "query_market_data",
        "run_backtest",
        "compute_metrics",
        "assemble_result_page",
    ]
    assert all(response.ok for _, response in results)
    assert dict(results)["run_backtest"].data["summary"]["trade_count"] > 0
    result_page = dict(results)["assemble_result_page"].data["result_page"]
    assert result_page["summary"]["strategy_name"] == "上月涨幅 TOP5 月度轮动策略"


def test_display_strategy_name_fallbacks_are_readable() -> None:
    assert display_strategy_name(macd_510300_schema()) == "沪深300ETF MACD"
    assert display_strategy_name(
        {
            "strategy_type": "cross_sectional_rotation",
            "selection": {"ranking": {"sort_by": "amount", "top_n": 20}},
            "portfolio": {"position_count": 20},
        }
    ) == "成交额 TOP20 月度轮动策略"


if __name__ == "__main__":
    test_macd_execution_flow_success()
    test_execution_flow_stops_on_invalid_signal_contract()
    test_monthly_amount_rotation_execution_flow_success()
    test_previous_month_return_rotation_execution_flow_success()
    test_display_strategy_name_fallbacks_are_readable()
    print("ok")
