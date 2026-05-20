from __future__ import annotations

import pandas as pd

from strategy_agent.data_access import (
    load_bar_frame,
    load_benchmark_frame,
    load_daily_basic_frame,
    resolve_latest_trade_date,
)
from .instruments import resolve_instrument


def get_latest_trade_date() -> str:
    return resolve_latest_trade_date()


def get_bar_frame(instrument: str, price_mode: str = "qfq", start_date: str | None = None, end_date: str = "latest") -> pd.DataFrame:
    resolved = resolve_instrument(instrument)
    if not resolved["resolved"] or not resolved["instrument"]:
        return pd.DataFrame()
    ts_code = str(resolved["instrument"]["ts_code"])
    return load_bar_frame(ts_code, price_mode=price_mode, start_date=start_date, end_date=end_date)


def get_benchmark_frame(symbol: str = "000300.SH", start_date: str | None = None, end_date: str = "latest") -> pd.DataFrame:
    return load_benchmark_frame(symbol, start_date=start_date, end_date=end_date)


def get_daily_basic_frame(trade_date: str = "latest") -> pd.DataFrame:
    return load_daily_basic_frame(trade_date)


def get_daily_basic_by_instrument(instrument: str, trade_date: str = "latest") -> pd.DataFrame:
    resolved = resolve_instrument(instrument)
    if not resolved["resolved"] or not resolved["instrument"]:
        return pd.DataFrame()
    code = str(resolved["instrument"]["ts_code"]).upper()
    frame = get_daily_basic_frame(trade_date)
    if frame.empty:
        return frame
    return frame[frame["ts_code"].astype(str).str.upper() == code].reset_index(drop=True)
