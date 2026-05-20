from __future__ import annotations

import math

from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse


def compute_metrics(backtest_result: dict, metrics_profile: str = "default_v1") -> ToolResponse[dict]:
    equity_curve = backtest_result.get("equity_curve") or []
    if not equity_curve:
        return ToolResponse(
            ok=False,
            error=ToolError(
                code="metrics_compute_failed",
                message="缺少 equity_curve，无法计算指标",
            ),
            meta={"metrics_profile": metrics_profile},
        )

    navs = [float(point["nav"]) for point in equity_curve if "nav" in point]
    if len(navs) < 2:
        return ToolResponse(
            ok=False,
            error=ToolError(code="metrics_compute_failed", message="净值点数量不足"),
            meta={"metrics_profile": metrics_profile},
        )

    total_return = navs[-1] / navs[0] - 1.0
    periods = len(navs)
    annualized_return = (navs[-1] / navs[0]) ** (252 / max(periods - 1, 1)) - 1.0
    running_peak = navs[0]
    max_drawdown = 0.0
    daily_returns = []
    for prev, curr in zip(navs[:-1], navs[1:]):
        if prev:
            daily_returns.append(curr / prev - 1.0)
        running_peak = max(running_peak, curr)
        if running_peak:
            max_drawdown = max(max_drawdown, 1.0 - curr / running_peak)
    if daily_returns:
        mean_ret = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_ret) ** 2 for r in daily_returns) / max(len(daily_returns), 1)
        volatility = math.sqrt(variance) * math.sqrt(252)
        sharpe = (mean_ret * 252) / volatility if volatility else 0.0
    else:
        volatility = 0.0
        sharpe = 0.0

    return ToolResponse(
        ok=True,
        data={
            "return_metrics": {
                "total_return": total_return,
                "annualized_return": annualized_return,
                "average_yearly_return": annualized_return,
            },
            "risk_metrics": {
                "max_drawdown": max_drawdown,
                "sharpe": sharpe,
                "volatility": volatility,
            },
            "trading_metrics": {
                "trade_count": len(backtest_result.get("trade_log") or []),
                "win_rate": None,
                "avg_holding_days": None,
                "turnover": None,
            },
            "period_breakdown": {
                "yearly_returns": backtest_result.get("yearly_returns") or [],
            },
        },
        meta={"metrics_profile": metrics_profile},
    )
