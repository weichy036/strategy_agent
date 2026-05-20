from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from typing import Any

import pandas as pd

from strategy_agent.config import settings
from strategy_agent.constants import (
    DEFAULT_COMMISSION_BPS,
    DEFAULT_ETF_SLIPPAGE_BPS,
    DEFAULT_STOCK_SLIPPAGE_BPS,
)
from strategy_agent.domain.market_data import get_bar_frame, get_benchmark_frame, get_daily_basic_frame
from strategy_agent.schemas.strategy_schema import SignalRule, StrategySchema


@dataclass
class ExecutedTrade:
    trade_date: str
    side: str
    symbol: str | None
    shares: float
    price: float
    nav_after: float


def _compute_macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    out = df.copy()
    close = out["close"].astype(float)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    out["macd_dif"] = ema_fast - ema_slow
    out["macd_dea"] = out["macd_dif"].ewm(span=signal, adjust=False).mean()
    out["macd_hist"] = out["macd_dif"] - out["macd_dea"]
    out["macd_bullish_cross"] = (out["macd_dif"] > out["macd_dea"]) & (
        out["macd_dif"].shift(1) <= out["macd_dea"].shift(1)
    )
    out["macd_bearish_cross"] = (out["macd_dif"] < out["macd_dea"]) & (
        out["macd_dif"].shift(1) >= out["macd_dea"].shift(1)
    )
    return out


def _apply_signal_rule(df: pd.DataFrame, rule: SignalRule) -> pd.Series:
    if rule.kind == "indicator_event" and rule.indicator == "macd":
        params = rule.params or {}
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal = int(params.get("signal", 9))
        if "macd_dif" not in df.columns:
            enriched = _compute_macd(df, fast=fast, slow=slow, signal=signal)
            for column in enriched.columns:
                if column not in df.columns:
                    df[column] = enriched[column]
                elif column.startswith("macd_"):
                    df[column] = enriched[column]
        if rule.operator == "bullish_cross":
            return df["macd_bullish_cross"].fillna(False)
        if rule.operator == "bearish_cross":
            return df["macd_bearish_cross"].fillna(False)
    if rule.kind == "comparison_rule":
        field = rule.indicator or rule.params.get("field") if rule.params else None
        value = rule.value
        if field and field in df.columns:
            series = df[field]
            if rule.operator == "gt":
                return series > value
            if rule.operator == "lt":
                return series < value
            if rule.operator == "eq":
                return series == value
    return pd.Series(False, index=df.index)


def _combine_rules(df: pd.DataFrame, rules: list[SignalRule]) -> pd.Series:
    if not rules:
        return pd.Series(False, index=df.index)
    combined = pd.Series(False, index=df.index)
    for rule in rules:
        combined = combined | _apply_signal_rule(df, rule)
    return combined.fillna(False)


def _slippage_bps(schema: StrategySchema, asset_type: str) -> float:
    if schema.costs is not None:
        return float(schema.costs.slippage_bps)
    return float(DEFAULT_ETF_SLIPPAGE_BPS if asset_type in {"fund", "etf"} else DEFAULT_STOCK_SLIPPAGE_BPS)


def _commission_bps(schema: StrategySchema) -> float:
    if schema.costs is not None:
        return float(schema.costs.commission_bps)
    return float(DEFAULT_COMMISSION_BPS)


def _to_pct(bps: float) -> float:
    return float(bps) / 10000.0


def _normalize_date(value: str | None) -> str:
    if not value:
        return ""
    return str(value).replace("-", "")


def _compute_yearly_returns(equity_curve: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _run_signal_strategy_backtest(schema: StrategySchema) -> dict[str, Any]:
    if schema.universe.type != "instrument" or len(schema.universe.symbols) != 1:
        raise ValueError("Current backtest engine only supports single-instrument strategies")
    if not schema.signals or not schema.signals.buy or not schema.signals.sell:
        raise ValueError("Current backtest engine requires both buy and sell signals")

    symbol = schema.universe.symbols[0].upper()
    price_mode = "raw" if symbol.startswith(("5", "1")) else "qfq"
    bars = get_bar_frame(symbol, price_mode=price_mode, start_date=schema.period.start, end_date=schema.period.end or "latest")
    if bars.empty:
        raise ValueError(f"No market data found for {symbol}")

    df = bars.copy().sort_values("trade_date").reset_index(drop=True)
    df["trade_date"] = df["trade_date"].astype(str)
    df["buy_signal"] = _combine_rules(df, schema.signals.buy)
    df["sell_signal"] = _combine_rules(df, schema.signals.sell)

    commission = _to_pct(_commission_bps(schema))
    slippage = _to_pct(_slippage_bps(schema, asset_type=str(df.iloc[0].get("asset_type", "stock"))))

    cash = 1.0
    shares = 0.0
    pending_action: str | None = None
    trade_log: list[dict[str, Any]] = []
    position_log: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        trade_date = str(row["trade_date"])
        open_price = float(row["open"])
        close_price = float(row["close"])

        if pending_action == "buy" and shares == 0.0 and open_price > 0:
            exec_price = open_price * (1.0 + slippage)
            investable_cash = cash * (1.0 - commission)
            shares = investable_cash / exec_price
            cash = 0.0
            trade_log.append(
                ExecutedTrade(
                    trade_date=trade_date,
                    side="buy",
                    symbol=symbol,
                    shares=float(shares),
                    price=exec_price,
                    nav_after=shares * close_price,
                ).__dict__
            )
        elif pending_action == "sell" and shares > 0.0 and open_price > 0:
            exec_price = open_price * (1.0 - slippage)
            cash = shares * exec_price * (1.0 - commission)
            shares = 0.0
            trade_log.append(
                ExecutedTrade(
                    trade_date=trade_date,
                    side="sell",
                    symbol=symbol,
                    shares=float(shares),
                    price=exec_price,
                    nav_after=cash,
                ).__dict__
            )
        pending_action = None

        nav = cash + shares * close_price
        equity_curve.append(
            {
                "trade_date": trade_date,
                "nav": float(nav),
                "position": 1 if shares > 0 else 0,
                "close": close_price,
            }
        )
        position_log.append(
            {
                "trade_date": trade_date,
                "position": 1 if shares > 0 else 0,
                "shares": float(shares),
                "cash": float(cash),
                "nav": float(nav),
            }
        )

        buy_signal = bool(row["buy_signal"])
        sell_signal = bool(row["sell_signal"])
        if shares == 0 and buy_signal:
            pending_action = "buy"
        elif shares > 0 and sell_signal:
            pending_action = "sell"

    nav_series = pd.Series([point["nav"] for point in equity_curve], index=[point["trade_date"] for point in equity_curve], dtype=float)
    running_peak = nav_series.cummax()
    drawdown_curve = [
        {"trade_date": date, "drawdown": float(1.0 - nav / peak) if peak else 0.0}
        for date, nav, peak in zip(nav_series.index, nav_series.values, running_peak.values)
    ]

    benchmark = get_benchmark_frame("000300.SH", start_date=schema.period.start, end_date=schema.period.end or "latest")
    benchmark_return = None
    if not benchmark.empty:
        benchmark = benchmark.sort_values("trade_date").reset_index(drop=True)
        start_close = float(benchmark.iloc[0]["close"])
        end_close = float(benchmark.iloc[-1]["close"])
        if start_close:
            benchmark_return = end_close / start_close - 1.0

    return {
        "run_id": f"bt_{symbol}_{df.iloc[0]['trade_date']}_{df.iloc[-1]['trade_date']}",
        "strategy_id": schema.strategy_id or schema.name or symbol,
        "date_range": {
            "start": schema.period.start or str(df.iloc[0]["trade_date"]),
            "end": schema.period.end or str(df.iloc[-1]["trade_date"]),
        },
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "trade_log": trade_log,
        "position_log": position_log,
        "yearly_returns": _compute_yearly_returns(equity_curve),
        "summary": {
            "final_nav": float(equity_curve[-1]["nav"]),
            "total_return": float(equity_curve[-1]["nav"] / equity_curve[0]["nav"] - 1.0),
            "benchmark_return": benchmark_return,
            "trade_count": len(trade_log),
        },
    }


def _list_monthly_rebalance_dates(start_date: str, end_date: str) -> list[str]:
    start = _normalize_date(start_date)
    end = _normalize_date(end_date)
    candidates = sorted(path.stem for path in settings.daily_basic_dir.glob("*.parquet"))
    in_range = [date for date in candidates if (not start or date >= start) and (not end or date <= end)]
    first_in_month: dict[str, str] = {}
    for date in in_range:
        month = date[:6]
        if month not in first_in_month:
            first_in_month[month] = date
    return [first_in_month[month] for month in sorted(first_in_month)]


def _select_top_symbols(schema: StrategySchema, rebalance_date: str) -> list[str]:
    if not schema.selection or not schema.selection.ranking:
        raise ValueError("Cross-sectional rotation requires selection.ranking")
    ranking = schema.selection.ranking
    sort_by = ranking.sort_by
    order_asc = ranking.order == "asc"
    top_n = int(schema.portfolio.position_count or ranking.top_n)

    frame = get_daily_basic_frame(rebalance_date)
    if frame.empty:
        return []
    if sort_by not in frame.columns:
        raise ValueError(f"Ranking field '{sort_by}' not found in daily_basic data")

    ranked = frame.copy()
    ranked = ranked[ranked[sort_by].notna()]
    if sort_by in {"total_mv", "circ_mv"}:
        ranked = ranked[ranked[sort_by].astype(float) > 0]
    ranked = ranked.sort_values(sort_by, ascending=order_asc)
    return ranked["ts_code"].astype(str).str.upper().head(top_n).tolist()


def _get_symbol_price_cache(
    cache: dict[str, pd.DataFrame],
    symbol: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    if symbol in cache:
        return cache[symbol]
    bars = get_bar_frame(symbol, price_mode="qfq", start_date=start_date, end_date=end_date)
    if bars.empty:
        cache[symbol] = pd.DataFrame(columns=["trade_date", "open", "close"])
        return cache[symbol]
    out = bars.copy()
    out["trade_date"] = out["trade_date"].astype(str)
    out = out.sort_values("trade_date").set_index("trade_date")
    cache[symbol] = out
    return out


def _run_cross_sectional_rotation_backtest(schema: StrategySchema) -> dict[str, Any]:
    if schema.universe.type != "equity_universe":
        raise ValueError("Cross-sectional rotation requires equity_universe")
    if not schema.selection or not schema.selection.ranking:
        raise ValueError("Cross-sectional rotation requires selection.ranking")
    if not schema.portfolio or not schema.portfolio.position_count:
        raise ValueError("Cross-sectional rotation requires portfolio.position_count")

    benchmark = get_benchmark_frame("000300.SH", start_date=schema.period.start, end_date=schema.period.end or "latest")
    if benchmark.empty:
        raise ValueError("Benchmark data is required for trading calendar")
    benchmark = benchmark.sort_values("trade_date").reset_index(drop=True)
    benchmark["trade_date"] = benchmark["trade_date"].astype(str)
    calendar = benchmark["trade_date"].tolist()
    if not calendar:
        raise ValueError("No trading dates found")

    start_date = _normalize_date(schema.period.start) or calendar[0]
    end_date = _normalize_date(schema.period.end) if schema.period.end and str(schema.period.end).lower() != "latest" else calendar[-1]
    calendar = [date for date in calendar if start_date <= date <= end_date]
    if len(calendar) < 2:
        raise ValueError("Trading calendar is too short for backtest")

    rebalance_signal_dates = _list_monthly_rebalance_dates(start_date, end_date)
    if not rebalance_signal_dates:
        raise ValueError("No rebalance dates found from daily_basic data")

    rebalance_plans: dict[str, list[str]] = {}
    for signal_date in rebalance_signal_dates:
        signal_idx = bisect_left(calendar, signal_date)
        exec_idx = signal_idx + 1
        if exec_idx >= len(calendar):
            continue
        exec_date = calendar[exec_idx]
        symbols = _select_top_symbols(schema, signal_date)
        if symbols:
            rebalance_plans[exec_date] = symbols

    if not rebalance_plans:
        raise ValueError("No valid rebalance plan generated")

    commission = _to_pct(_commission_bps(schema))
    slippage = _to_pct(_slippage_bps(schema, asset_type="stock"))
    price_cache: dict[str, pd.DataFrame] = {}
    last_close: dict[str, float] = {}

    cash = 1.0
    holdings: dict[str, float] = {}
    trade_log: list[dict[str, Any]] = []
    position_log: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = []

    for trade_date in calendar:
        target_symbols = rebalance_plans.get(trade_date)
        if target_symbols is not None:
            for symbol, shares in list(holdings.items()):
                frame = _get_symbol_price_cache(price_cache, symbol, start_date, end_date)
                if trade_date not in frame.index:
                    continue
                open_price = float(frame.at[trade_date, "open"])
                if open_price <= 0:
                    continue
                exec_price = open_price * (1.0 - slippage)
                proceeds = shares * exec_price * (1.0 - commission)
                cash += proceeds
                trade_log.append(
                    ExecutedTrade(
                        trade_date=trade_date,
                        side="sell",
                        symbol=symbol,
                        shares=float(shares),
                        price=float(exec_price),
                        nav_after=float(cash),
                    ).__dict__
                )
                holdings.pop(symbol, None)

            tradable_targets: list[tuple[str, float]] = []
            for symbol in target_symbols:
                frame = _get_symbol_price_cache(price_cache, symbol, start_date, end_date)
                if trade_date not in frame.index:
                    continue
                open_price = float(frame.at[trade_date, "open"])
                if open_price > 0:
                    tradable_targets.append((symbol, open_price))

            if tradable_targets:
                allocation = cash / len(tradable_targets)
                for symbol, open_price in tradable_targets:
                    exec_price = open_price * (1.0 + slippage)
                    buy_cash = allocation * (1.0 - commission)
                    shares = buy_cash / exec_price if exec_price > 0 else 0.0
                    spent = shares * exec_price
                    cash -= spent
                    holdings[symbol] = holdings.get(symbol, 0.0) + shares
                    trade_log.append(
                        ExecutedTrade(
                            trade_date=trade_date,
                            side="buy",
                            symbol=symbol,
                            shares=float(shares),
                            price=float(exec_price),
                            nav_after=float(cash),
                        ).__dict__
                    )

        nav = cash
        for symbol, shares in holdings.items():
            frame = _get_symbol_price_cache(price_cache, symbol, start_date, end_date)
            if trade_date in frame.index:
                close_price = float(frame.at[trade_date, "close"])
                last_close[symbol] = close_price
            elif symbol in last_close:
                close_price = float(last_close[symbol])
            else:
                continue
            nav += shares * close_price

        equity_curve.append(
            {
                "trade_date": trade_date,
                "nav": float(nav),
                "position": len(holdings),
                "close": float(benchmark.loc[benchmark["trade_date"] == trade_date, "close"].iloc[0]),
            }
        )
        position_log.append(
            {
                "trade_date": trade_date,
                "holding_count": len(holdings),
                "cash": float(cash),
                "nav": float(nav),
                "symbols": sorted(list(holdings.keys()))[:50],
            }
        )

    if not equity_curve:
        raise ValueError("No equity curve generated")

    nav_series = pd.Series([point["nav"] for point in equity_curve], index=[point["trade_date"] for point in equity_curve], dtype=float)
    running_peak = nav_series.cummax()
    drawdown_curve = [
        {"trade_date": date, "drawdown": float(1.0 - nav / peak) if peak else 0.0}
        for date, nav, peak in zip(nav_series.index, nav_series.values, running_peak.values)
    ]

    start_close = float(benchmark.iloc[0]["close"])
    end_close = float(benchmark.iloc[-1]["close"])
    benchmark_return = (end_close / start_close - 1.0) if start_close else None

    return {
        "run_id": f"bt_rotation_{calendar[0]}_{calendar[-1]}",
        "strategy_id": schema.strategy_id or schema.name or "rotation",
        "date_range": {"start": calendar[0], "end": calendar[-1]},
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "trade_log": trade_log,
        "position_log": position_log,
        "yearly_returns": _compute_yearly_returns(equity_curve),
        "summary": {
            "final_nav": float(equity_curve[-1]["nav"]),
            "total_return": float(equity_curve[-1]["nav"] / equity_curve[0]["nav"] - 1.0),
            "benchmark_return": benchmark_return,
            "trade_count": len(trade_log),
        },
    }


def run_backtest_for_strategy(schema: StrategySchema) -> dict[str, Any]:
    if schema.strategy_type in {"signal_trading", "rule_based_timing"}:
        return _run_signal_strategy_backtest(schema)
    if schema.strategy_type == "cross_sectional_rotation":
        return _run_cross_sectional_rotation_backtest(schema)
    raise ValueError(f"Unsupported strategy type for current engine: {schema.strategy_type}")
