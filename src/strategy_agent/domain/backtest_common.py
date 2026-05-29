from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from strategy_agent.constants import (
    DEFAULT_COMMISSION_BPS,
    DEFAULT_ETF_SLIPPAGE_BPS,
    DEFAULT_STOCK_SLIPPAGE_BPS,
)
from strategy_agent.schemas.strategy_schema import StrategySchema


@dataclass
class ExecutedTrade:
    trade_date: str
    side: str
    symbol: str | None
    shares: float
    price: float
    nav_after: float


def slippage_pct(schema: StrategySchema, asset_type: str) -> float:
    if schema.costs is not None:
        return bps_to_pct(float(schema.costs.slippage_bps))
    default = DEFAULT_ETF_SLIPPAGE_BPS if asset_type in {"fund", "etf"} else DEFAULT_STOCK_SLIPPAGE_BPS
    return bps_to_pct(float(default))


def commission_pct(schema: StrategySchema) -> float:
    if schema.costs is not None:
        return bps_to_pct(float(schema.costs.commission_bps))
    return bps_to_pct(float(DEFAULT_COMMISSION_BPS))


def bps_to_pct(bps: float) -> float:
    return float(bps) / 10000.0


def normalize_date(value: str | None) -> str:
    if not value:
        return ""
    return str(value).replace("-", "")


def yearly_returns(equity_curve: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not equity_curve:
        return []
    frame = pd.DataFrame(equity_curve)
    frame["trade_date"] = frame["trade_date"].astype(str)
    frame["year"] = frame["trade_date"].str[:4]
    yearly = []
    for year, group in frame.groupby("year"):
        group = group.sort_values("trade_date")
        start_nav = float(group.iloc[0]["nav"])
        end_nav = float(group.iloc[-1]["nav"])
        yearly.append({"year": year, "return": end_nav / start_nav - 1.0})
    return yearly


def drawdown_curve(equity_curve: list[dict[str, Any]]) -> list[dict[str, float | str]]:
    nav_series = pd.Series(
        [point["nav"] for point in equity_curve],
        index=[point["trade_date"] for point in equity_curve],
        dtype=float,
    )
    running_peak = nav_series.cummax()
    return [
        {"trade_date": date, "drawdown": float(1.0 - nav / peak) if peak else 0.0}
        for date, nav, peak in zip(nav_series.index, nav_series.values, running_peak.values)
    ]


__all__ = [
    "ExecutedTrade",
    "commission_pct",
    "drawdown_curve",
    "normalize_date",
    "slippage_pct",
    "yearly_returns",
]
