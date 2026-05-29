from __future__ import annotations

from typing import Any

import pandas as pd

from strategy_agent.domain.backtest_common import (
    ExecutedTrade,
    commission_pct,
    drawdown_curve,
    slippage_pct,
    yearly_returns,
)
from strategy_agent.domain.market_data import get_bar_frame, get_benchmark_frame
from strategy_agent.schemas.strategy_schema import SignalRule, StrategySchema


def run_signal_backtest(schema: StrategySchema) -> dict[str, Any]:
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

    commission = commission_pct(schema)
    slippage = slippage_pct(schema, asset_type=str(df.iloc[0].get("asset_type", "stock")))

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
                ExecutedTrade(trade_date, "buy", symbol, float(shares), exec_price, shares * close_price).__dict__
            )
        elif pending_action == "sell" and shares > 0.0 and open_price > 0:
            exec_price = open_price * (1.0 - slippage)
            sold_shares = shares
            cash = sold_shares * exec_price * (1.0 - commission)
            shares = 0.0
            trade_log.append(
                ExecutedTrade(trade_date, "sell", symbol, float(sold_shares), exec_price, cash).__dict__
            )
        pending_action = None

        nav = cash + shares * close_price
        equity_curve.append({"trade_date": trade_date, "nav": float(nav), "position": 1 if shares > 0 else 0, "close": close_price})
        position_log.append({"trade_date": trade_date, "position": 1 if shares > 0 else 0, "shares": float(shares), "cash": float(cash), "nav": float(nav)})

        if shares == 0 and bool(row["buy_signal"]):
            pending_action = "buy"
        elif shares > 0 and bool(row["sell_signal"]):
            pending_action = "sell"

    benchmark_return = _benchmark_return(schema)
    return {
        "run_id": f"bt_{symbol}_{df.iloc[0]['trade_date']}_{df.iloc[-1]['trade_date']}",
        "strategy_id": schema.strategy_id or schema.name or symbol,
        "date_range": {
            "start": schema.period.start or str(df.iloc[0]["trade_date"]),
            "end": schema.period.end or str(df.iloc[-1]["trade_date"]),
        },
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve(equity_curve),
        "trade_log": trade_log,
        "position_log": position_log,
        "yearly_returns": yearly_returns(equity_curve),
        "summary": {
            "final_nav": float(equity_curve[-1]["nav"]),
            "total_return": float(equity_curve[-1]["nav"] / equity_curve[0]["nav"] - 1.0),
            "benchmark_return": benchmark_return,
            "trade_count": len(trade_log),
        },
    }


def _compute_macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> pd.DataFrame:
    out = df.copy()
    close = out["close"].astype(float)
    out["macd_dif"] = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    out["macd_dea"] = out["macd_dif"].ewm(span=signal, adjust=False).mean()
    out["macd_hist"] = out["macd_dif"] - out["macd_dea"]
    out["macd_bullish_cross"] = (out["macd_dif"] > out["macd_dea"]) & (out["macd_dif"].shift(1) <= out["macd_dea"].shift(1))
    out["macd_bearish_cross"] = (out["macd_dif"] < out["macd_dea"]) & (out["macd_dif"].shift(1) >= out["macd_dea"].shift(1))
    return out


def _apply_signal_rule(df: pd.DataFrame, rule: SignalRule) -> pd.Series:
    if rule.kind == "indicator_event" and rule.indicator == "macd":
        params = rule.params or {}
        enriched = _compute_macd(df, int(params.get("fast", 12)), int(params.get("slow", 26)), int(params.get("signal", 9)))
        for column in enriched.columns:
            if column not in df.columns or column.startswith("macd_"):
                df[column] = enriched[column]
        if rule.operator == "bullish_cross":
            return df["macd_bullish_cross"].fillna(False)
        if rule.operator == "bearish_cross":
            return df["macd_bearish_cross"].fillna(False)

    if rule.kind == "comparison_rule":
        field = rule.indicator or rule.params.get("field") if rule.params else None
        if field and field in df.columns:
            if rule.operator == "gt":
                return df[field] > rule.value
            if rule.operator == "lt":
                return df[field] < rule.value
            if rule.operator == "eq":
                return df[field] == rule.value
    return pd.Series(False, index=df.index)


def _combine_rules(df: pd.DataFrame, rules: list[SignalRule]) -> pd.Series:
    combined = pd.Series(False, index=df.index)
    for rule in rules:
        combined = combined | _apply_signal_rule(df, rule)
    return combined.fillna(False)


def _benchmark_return(schema: StrategySchema) -> float | None:
    benchmark = get_benchmark_frame("000300.SH", start_date=schema.period.start, end_date=schema.period.end or "latest")
    if benchmark.empty:
        return None
    benchmark = benchmark.sort_values("trade_date").reset_index(drop=True)
    start_close = float(benchmark.iloc[0]["close"])
    end_close = float(benchmark.iloc[-1]["close"])
    return end_close / start_close - 1.0 if start_close else None


__all__ = ["run_signal_backtest"]
