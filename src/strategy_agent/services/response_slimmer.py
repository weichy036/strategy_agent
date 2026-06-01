from __future__ import annotations

from copy import deepcopy
from typing import Any

from strategy_agent.services.runtime_models import AgentTurnResult


def slim_turn_result(result: AgentTurnResult) -> AgentTurnResult:
    return AgentTurnResult(
        status=result.status,
        assistant_message=result.assistant_message,
        data=slim_response_data(result.data),
        tool_calls=slim_tool_calls(result.tool_calls),
        timeline=result.timeline,
    )


def slim_response_data(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}

    slimmed = deepcopy(data)
    if isinstance(slimmed.get("backtest"), dict):
        slimmed["backtest"] = _slim_backtest(slimmed["backtest"])
    if isinstance(slimmed.get("result_page"), dict):
        slimmed["result_page"] = _slim_result_page(slimmed["result_page"])
    return slimmed


def slim_tool_calls(tool_calls: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(tool_calls, list):
        return []

    slimmed = []
    for item in tool_calls:
        call = deepcopy(item)
        payload = call.get("payload")
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict) and _looks_like_backtest(data):
                payload["data"] = _slim_backtest(data)
            elif isinstance(data, dict) and isinstance(data.get("result_page"), dict):
                payload["data"]["result_page"] = _slim_result_page(data["result_page"])
        slimmed.append(call)
    return slimmed


def _slim_backtest(backtest: dict[str, Any]) -> dict[str, Any]:
    equity_curve = _as_list(backtest.get("equity_curve"))
    drawdown_curve = _as_list(backtest.get("drawdown_curve"))
    trade_log = _as_list(backtest.get("trade_log"))
    position_log = _as_list(backtest.get("position_log"))
    selection_log = _as_list(backtest.get("selection_log"))

    return {
        "run_id": backtest.get("run_id"),
        "strategy_id": backtest.get("strategy_id"),
        "date_range": backtest.get("date_range") or {},
        "summary": backtest.get("summary") or {},
        "yearly_returns": backtest.get("yearly_returns") or [],
        "data_size": {
            "equity_curve_points": len(equity_curve),
            "drawdown_points": len(drawdown_curve),
            "trade_log_rows": len(trade_log),
            "position_log_rows": len(position_log),
            "selection_log_rows": len(selection_log),
        },
        "equity_curve": _series_meta(equity_curve),
        "drawdown_curve": _series_meta(drawdown_curve, value_key="drawdown"),
    }


def _slim_result_page(result_page: dict[str, Any]) -> dict[str, Any]:
    page = deepcopy(result_page)
    equity = page.get("equity_curve")
    if isinstance(equity, dict):
        series = _as_list(equity.get("series"))
        page["equity_curve"] = {
            "artifact": equity.get("artifact"),
            "meta": _series_meta(series),
        }

    drawdown = page.get("drawdown_curve")
    if isinstance(drawdown, dict):
        series = _as_list(drawdown.get("series"))
        page["drawdown_curve"] = {"meta": _series_meta(series, value_key="drawdown")}

    return page


def _series_meta(series: list[dict[str, Any]], *, value_key: str = "nav") -> dict[str, Any]:
    if not series:
        return {"point_count": 0}
    first = series[0]
    last = series[-1]
    return {
        "point_count": len(series),
        "start_date": first.get("trade_date"),
        "end_date": last.get("trade_date"),
        f"start_{value_key}": first.get(value_key),
        f"end_{value_key}": last.get(value_key),
    }


def _looks_like_backtest(data: dict[str, Any]) -> bool:
    return any(key in data for key in ("equity_curve", "drawdown_curve", "trade_log", "selection_log"))


def _as_list(value: Any) -> list[dict[str, Any]]:
    return value if isinstance(value, list) else []


__all__ = ["slim_response_data", "slim_tool_calls", "slim_turn_result"]
