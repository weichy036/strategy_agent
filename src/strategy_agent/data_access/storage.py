from __future__ import annotations

from pathlib import Path

from strategy_agent.config import settings


def fund_daily_path(ts_code: str) -> Path:
    return settings.fund_daily_dir / f"{ts_code.upper()}.parquet"


def index_daily_path(ts_code: str) -> Path:
    return settings.index_daily_dir / f"{ts_code.upper()}.parquet"


def daily_qfq_path(ts_code: str) -> Path:
    return settings.daily_qfq_dir / f"{ts_code.upper()}.parquet"


def daily_basic_path(trade_date: str) -> Path:
    return settings.daily_basic_dir / f"{trade_date}.parquet"


def selection_daily_path(trade_date: str) -> Path:
    return settings.selection_daily_dir / f"{trade_date}.parquet"


def selection_monthly_path(month: str, field: str) -> Path:
    return settings.selection_monthly_dir / f"{month}_{field}_sum.parquet"
