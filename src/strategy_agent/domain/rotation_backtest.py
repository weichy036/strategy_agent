from __future__ import annotations

from bisect import bisect_left
from typing import Any

import pandas as pd

from strategy_agent.data_access.selection_daily import (
    ensure_selection_daily_frames,
    ensure_selection_monthly_returns,
    load_selection_monthly_return,
    load_selection_monthly_sum,
)
from strategy_agent.config import settings
from strategy_agent.domain.backtest_common import (
    ExecutedTrade,
    commission_pct,
    drawdown_curve,
    normalize_date,
    slippage_pct,
    yearly_returns,
)
from strategy_agent.domain.market_data import get_bar_frame, get_benchmark_frame, get_selection_daily_frame
from strategy_agent.schemas.strategy_schema import StrategySchema


def run_rotation_backtest(schema: StrategySchema) -> dict[str, Any]:
    if schema.universe.type != "equity_universe":
        raise ValueError("Cross-sectional rotation requires equity_universe")
    if not schema.selection or not schema.selection.ranking:
        raise ValueError("Cross-sectional rotation requires selection.ranking")
    if not schema.portfolio or not schema.portfolio.position_count:
        raise ValueError("Cross-sectional rotation requires portfolio.position_count")

    benchmark = _load_calendar(schema)
    calendar = _calendar_window(benchmark, schema)
    rebalance_plans = _build_rebalance_plans(schema, calendar)
    if not rebalance_plans:
        raise ValueError("No valid rebalance plan generated")

    commission = commission_pct(schema)
    slippage = slippage_pct(schema, asset_type="stock")
    price_cache: dict[str, pd.DataFrame] = {}
    last_close: dict[str, float] = {}
    cash = 1.0
    holdings: dict[str, float] = {}
    trade_log: list[dict[str, Any]] = []
    position_log: list[dict[str, Any]] = []
    selection_log: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []

    for trade_date in calendar:
        target_symbols = rebalance_plans.get(trade_date)
        if target_symbols is not None:
            cash = _sell_all(trade_date, holdings, cash, price_cache, start_date=calendar[0], end_date=calendar[-1], commission=commission, slippage=slippage, trade_log=trade_log)
            cash = _buy_targets(trade_date, target_symbols, holdings, cash, price_cache, start_date=calendar[0], end_date=calendar[-1], commission=commission, slippage=slippage, trade_log=trade_log)
            selection_log.append({
                "trade_date": trade_date,
                "target_count": len(target_symbols),
                "executed_count": len(holdings),
                "symbols": sorted(list(holdings.keys()))[:50],
            })

        nav = _portfolio_nav(trade_date, cash, holdings, price_cache, last_close, start_date=calendar[0], end_date=calendar[-1])
        equity_curve.append({
            "trade_date": trade_date,
            "nav": float(nav),
            "position": len(holdings),
            "close": float(benchmark.loc[benchmark["trade_date"] == trade_date, "close"].iloc[0]),
        })
        position_log.append({
            "trade_date": trade_date,
            "holding_count": len(holdings),
            "cash": float(cash),
            "nav": float(nav),
            "symbols": sorted(list(holdings.keys()))[:50],
        })

    if not equity_curve:
        raise ValueError("No equity curve generated")
    return _result(schema, calendar, benchmark, equity_curve, trade_log, position_log, selection_log)


def _sell_all(
    trade_date: str,
    holdings: dict[str, float],
    cash: float,
    price_cache: dict[str, pd.DataFrame],
    *,
    start_date: str,
    end_date: str,
    commission: float,
    slippage: float,
    trade_log: list[dict[str, Any]],
) -> float:
    for symbol, shares in list(holdings.items()):
        frame = _price_frame(price_cache, symbol, start_date, end_date)
        if trade_date not in frame.index:
            continue
        open_price = float(frame.at[trade_date, "open"])
        if open_price <= 0:
            continue
        exec_price = open_price * (1.0 - slippage)
        cash += shares * exec_price * (1.0 - commission)
        trade_log.append(ExecutedTrade(trade_date, "sell", symbol, float(shares), float(exec_price), float(cash)).__dict__)
        holdings.pop(symbol, None)
    return cash


def _buy_targets(
    trade_date: str,
    target_symbols: list[str],
    holdings: dict[str, float],
    cash: float,
    price_cache: dict[str, pd.DataFrame],
    *,
    start_date: str,
    end_date: str,
    commission: float,
    slippage: float,
    trade_log: list[dict[str, Any]],
) -> float:
    tradable = []
    for symbol in target_symbols:
        frame = _price_frame(price_cache, symbol, start_date, end_date)
        if trade_date in frame.index and float(frame.at[trade_date, "open"]) > 0:
            tradable.append((symbol, float(frame.at[trade_date, "open"])))
    if not tradable:
        return cash

    allocation = cash / len(tradable)
    for symbol, open_price in tradable:
        exec_price = open_price * (1.0 + slippage)
        shares = allocation / (exec_price * (1.0 + commission))
        cost = shares * exec_price
        fee = cost * commission
        cash -= cost + fee
        holdings[symbol] = holdings.get(symbol, 0.0) + shares
        trade_log.append(ExecutedTrade(trade_date, "buy", symbol, float(shares), float(exec_price), float(cash)).__dict__)
    return cash


def _portfolio_nav(
    trade_date: str,
    cash: float,
    holdings: dict[str, float],
    price_cache: dict[str, pd.DataFrame],
    last_close: dict[str, float],
    *,
    start_date: str,
    end_date: str,
) -> float:
    nav = cash
    for symbol, shares in holdings.items():
        frame = _price_frame(price_cache, symbol, start_date, end_date)
        if trade_date in frame.index:
            close_price = float(frame.at[trade_date, "close"])
            last_close[symbol] = close_price
        elif symbol in last_close:
            close_price = float(last_close[symbol])
        else:
            continue
        nav += shares * close_price
    return nav


def _load_calendar(schema: StrategySchema) -> pd.DataFrame:
    benchmark = get_benchmark_frame("000300.SH", start_date=schema.period.start, end_date=schema.period.end or "latest")
    if benchmark.empty:
        raise ValueError("Benchmark data is required for trading calendar")
    benchmark = benchmark.sort_values("trade_date").reset_index(drop=True)
    benchmark["trade_date"] = benchmark["trade_date"].astype(str)
    return benchmark


def _calendar_window(benchmark: pd.DataFrame, schema: StrategySchema) -> list[str]:
    calendar = benchmark["trade_date"].tolist()
    end_date = normalize_date(schema.period.end) if schema.period.end and str(schema.period.end).lower() != "latest" else calendar[-1]
    start_date = normalize_date(schema.period.start) or _default_rotation_start(calendar, end_date)
    calendar = [date for date in calendar if start_date <= date <= end_date]
    if len(calendar) < 2:
        raise ValueError("Trading calendar is too short for backtest")
    return calendar


def _default_rotation_start(calendar: list[str], end_date: str) -> str:
    target = f"{int(end_date[:4]) - 3}{end_date[4:]}"
    candidates = [date for date in calendar if date >= target]
    return candidates[0] if candidates else calendar[0]


def _build_rebalance_plans(schema: StrategySchema, calendar: list[str]) -> dict[str, list[str]]:
    plans: dict[str, list[str]] = {}
    signal_dates = _monthly_rebalance_dates(calendar[0], calendar[-1])
    ensure_selection_daily_frames(signal_dates)
    ranking = schema.selection.ranking
    if ranking.sort_by == "monthly_return":
        ensure_selection_monthly_returns([_previous_month(date) for date in signal_dates])
    for signal_date in signal_dates:
        exec_idx = bisect_left(calendar, signal_date) + 1
        if exec_idx >= len(calendar):
            continue
        symbols = _select_top_symbols(schema, signal_date)
        if symbols:
            plans[calendar[exec_idx]] = symbols
    return plans


def _monthly_rebalance_dates(start_date: str, end_date: str) -> list[str]:
    start = normalize_date(start_date)
    end = normalize_date(end_date)
    candidates = sorted(path.stem for path in settings.daily_basic_dir.glob("*.parquet"))
    in_range = [date for date in candidates if (not start or date >= start) and (not end or date <= end)]
    first_in_month: dict[str, str] = {}
    for date in in_range:
        first_in_month.setdefault(date[:6], date)
    return [first_in_month[month] for month in sorted(first_in_month)]


def _select_top_symbols(schema: StrategySchema, rebalance_date: str) -> list[str]:
    ranking = schema.selection.ranking
    sort_by = ranking.sort_by
    top_n = int(schema.portfolio.position_count or ranking.top_n)
    frame = _ranking_frame(ranking, rebalance_date)
    if frame.empty:
        return []
    if sort_by not in frame.columns:
        raise ValueError(f"Ranking field '{sort_by}' not found in selection_daily data")
    ranked = frame[frame[sort_by].notna()].copy()
    if sort_by in {"total_mv", "circ_mv"}:
        ranked = ranked[ranked[sort_by].astype(float) > 0]
    ranked = ranked.sort_values(sort_by, ascending=ranking.order == "asc")
    return ranked["ts_code"].astype(str).str.upper().head(top_n).tolist()


def _ranking_frame(ranking, rebalance_date: str) -> pd.DataFrame:
    if ranking.sort_by == "monthly_return":
        return load_selection_monthly_return(_previous_month(rebalance_date))
    if getattr(ranking, "lookback", "point_in_time") == "previous_month_sum":
        return load_selection_monthly_sum(_previous_month(rebalance_date), ranking.sort_by)
    return get_selection_daily_frame(rebalance_date)


def _previous_month(trade_date: str) -> str:
    year = int(trade_date[:4])
    month = int(trade_date[4:6])
    if month == 1:
        return f"{year - 1}12"
    return f"{year}{month - 1:02d}"


def _price_frame(cache: dict[str, pd.DataFrame], symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    if symbol in cache:
        return cache[symbol]
    bars = get_bar_frame(symbol, price_mode="qfq", start_date=start_date, end_date=end_date)
    if bars.empty:
        cache[symbol] = pd.DataFrame(columns=["trade_date", "open", "close"])
    else:
        cache[symbol] = bars.assign(trade_date=bars["trade_date"].astype(str)).sort_values("trade_date").set_index("trade_date")
    return cache[symbol]


def _result(
    schema: StrategySchema,
    calendar: list[str],
    benchmark: pd.DataFrame,
    equity_curve: list[dict[str, Any]],
    trade_log: list[dict[str, Any]],
    position_log: list[dict[str, Any]],
    selection_log: list[dict[str, Any]],
) -> dict[str, Any]:
    start_close = float(benchmark.iloc[0]["close"])
    end_close = float(benchmark.iloc[-1]["close"])
    return {
        "run_id": f"bt_rotation_{calendar[0]}_{calendar[-1]}",
        "strategy_id": schema.strategy_id or schema.name or "rotation",
        "date_range": {"start": calendar[0], "end": calendar[-1]},
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve(equity_curve),
        "trade_log": trade_log,
        "position_log": position_log,
        "selection_log": selection_log,
        "yearly_returns": yearly_returns(equity_curve),
        "summary": {
            "final_nav": float(equity_curve[-1]["nav"]),
            "total_return": float(equity_curve[-1]["nav"] / equity_curve[0]["nav"] - 1.0),
            "benchmark_return": (end_close / start_close - 1.0) if start_close else None,
            "trade_count": len(trade_log),
        },
    }


__all__ = ["run_rotation_backtest"]
