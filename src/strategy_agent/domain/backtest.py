from __future__ import annotations

from typing import Any

from strategy_agent.domain.rotation_backtest import run_rotation_backtest
from strategy_agent.domain.signal_backtest import run_signal_backtest
from strategy_agent.schemas.strategy_schema import StrategySchema


def run_backtest_for_strategy(schema: StrategySchema) -> dict[str, Any]:
    if schema.strategy_type in {"signal_trading", "rule_based_timing"}:
        return run_signal_backtest(schema)
    if schema.strategy_type == "cross_sectional_rotation":
        return run_rotation_backtest(schema)
    raise ValueError(f"Unsupported strategy type for current engine: {schema.strategy_type}")


__all__ = ["run_backtest_for_strategy"]
