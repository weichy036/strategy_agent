from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Callable

from strategy_agent.schemas.tool_contracts import ToolResponse
from strategy_agent.tools import (
    assemble_result_page,
    compute_metrics,
    query_market_data,
    run_backtest,
    validate_strategy_schema,
)
from strategy_agent.tools.report_assembly import display_strategy_name


@dataclass(frozen=True)
class ExecutionStep:
    name: str
    args: dict[str, Any]
    run: Callable[[], ToolResponse | dict[str, Any]]


def strategy_execution_steps(strategy_schema: dict[str, Any], session_id: str | None = None) -> Iterator[ExecutionStep]:
    state: dict[str, Any] = {}

    yield ExecutionStep(
        name="validate_strategy_schema",
        args={"strategy_schema": strategy_schema},
        run=lambda: _store(state, "validation", validate_strategy_schema(strategy_schema)),
    )
    if not _validation_passed(state):
        return

    yield ExecutionStep(
        name="query_market_data",
        args={"query_type": "latest_trade_date"},
        run=lambda: _store(state, "market_data", query_market_data("latest_trade_date")),
    )

    yield ExecutionStep(
        name="run_backtest",
        args={"strategy_schema": strategy_schema},
        run=lambda: _store(state, "backtest", run_backtest(strategy_schema)),
    )
    if not _response_ok(state.get("backtest")):
        return

    yield ExecutionStep(
        name="compute_metrics",
        args={"backtest_result": {"run_id": ((state["backtest"].data or {}).get("run_id"))}},
        run=lambda: _store(state, "metrics", compute_metrics(state["backtest"].data or {})),
    )
    if not _response_ok(state.get("metrics")):
        return

    yield ExecutionStep(
        name="assemble_result_page",
        args={"strategy_schema": strategy_schema},
        run=lambda: assemble_result_page(
            strategy_schema=strategy_schema,
            backtest_result=state["backtest"].data or {},
            metrics=state["metrics"].data or {},
            explanations=default_explanations(strategy_schema, state["metrics"].data or {}),
            session_id=session_id,
        ),
    )


def default_explanations(strategy_schema: dict[str, Any], metrics: dict[str, Any]) -> dict[str, str]:
    name = display_strategy_name(strategy_schema)
    annual = ((metrics.get("return_metrics") or {}).get("annualized_return") or 0.0) * 100
    drawdown = ((metrics.get("risk_metrics") or {}).get("max_drawdown") or 0.0) * 100
    return {
        "summary_text": f"{name} 回测完成，年化收益约 {annual:.2f}%，最大回撤约 {drawdown:.2f}%。",
        "risk_text": "回测结果基于历史数据，不代表未来表现。",
        "limitations_text": "当前结果未构成投资建议，仍需结合交易成本、流动性和参数稳定性复核。",
    }


def _store(state: dict[str, Any], key: str, response: ToolResponse | dict[str, Any]) -> ToolResponse | dict[str, Any]:
    state[key] = response
    return response


def _validation_passed(state: dict[str, Any]) -> bool:
    response = state.get("validation")
    if not _response_ok(response):
        return False
    data = response.data or {}
    return bool(data.get("is_valid") and data.get("is_complete"))


def _response_ok(response: Any) -> bool:
    return bool(getattr(response, "ok", False))


__all__ = ["ExecutionStep", "default_explanations", "strategy_execution_steps"]
