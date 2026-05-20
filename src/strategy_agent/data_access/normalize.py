from __future__ import annotations

from pathlib import Path

import pandas as pd

from strategy_agent.config import settings
from strategy_agent.constants import DEFAULT_INDEX_ALIASES
from .storage import daily_basic_path, daily_qfq_path, fund_daily_path, index_daily_path


def _slice_by_date(df: pd.DataFrame, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    if df.empty or "trade_date" not in df.columns:
        return df
    out = df.copy()
    out["trade_date"] = out["trade_date"].astype(str)
    if start_date:
        out = out[out["trade_date"] >= str(start_date).replace("-", "")]
    if end_date and str(end_date).lower() != "latest":
        out = out[out["trade_date"] <= str(end_date).replace("-", "")]
    return out.sort_values("trade_date").reset_index(drop=True)


def _read_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def resolve_latest_trade_date() -> str:
    candidates = [
        settings.fund_daily_dir,
        settings.index_daily_dir,
        settings.daily_qfq_dir,
    ]
    latest = ""
    for base in candidates:
        for path in sorted(base.glob("*.parquet"))[:20]:
            try:
                df = pd.read_parquet(path, columns=["trade_date"])
            except Exception:
                continue
            if df.empty:
                continue
            trade_date = str(df["trade_date"].max())
            if trade_date > latest:
                latest = trade_date
    return latest


def load_bar_frame(ts_code: str, price_mode: str = "qfq", start_date: str | None = None, end_date: str = "latest") -> pd.DataFrame:
    code = ts_code.upper()
    index_df = _read_if_exists(index_daily_path(code))
    if not index_df.empty:
        index_df = index_df.copy()
        index_df["ts_code"] = code
        index_df["asset_type"] = "index"
        index_df["price_mode"] = "raw"
        index_df["market"] = "CN_A"
        return _slice_by_date(index_df, start_date, end_date)

    fund_df = _read_if_exists(fund_daily_path(code))
    if not fund_df.empty:
        fund_df = fund_df.copy()
        fund_df["ts_code"] = code
        fund_df["asset_type"] = "fund"
        fund_df["price_mode"] = "raw"
        fund_df["market"] = "CN_A"
        if "vol" in fund_df.columns and "volume" not in fund_df.columns:
            fund_df["volume"] = fund_df["vol"]
        return _slice_by_date(fund_df, start_date, end_date)

    stock_df = _read_if_exists(daily_qfq_path(code))
    if stock_df.empty:
        return stock_df
    stock_df = stock_df.copy()
    stock_df["ts_code"] = code
    stock_df["asset_type"] = "stock"
    stock_df["price_mode"] = price_mode
    stock_df["market"] = "CN_A"
    return _slice_by_date(stock_df, start_date, end_date)


def load_benchmark_frame(symbol: str = "000300.SH", start_date: str | None = None, end_date: str = "latest") -> pd.DataFrame:
    code = DEFAULT_INDEX_ALIASES.get(symbol.lower(), symbol).upper()
    return load_bar_frame(code, price_mode="raw", start_date=start_date, end_date=end_date)


def load_daily_basic_frame(trade_date: str = "latest") -> pd.DataFrame:
    target = str(trade_date).strip()
    if not target or target.lower() == "latest":
        files = sorted(settings.daily_basic_dir.glob("*.parquet"), reverse=True)
        path = files[0] if files else None
    else:
        normalized = target.replace("-", "")
        path = daily_basic_path(normalized)
        if not path.exists():
            files = sorted([p for p in settings.daily_basic_dir.glob("*.parquet") if p.stem <= normalized], reverse=True)
            path = files[0] if files else None
    if path is None or not path.exists():
        return pd.DataFrame()
    out = pd.read_parquet(path)
    if out.empty:
        return out
    out = out.copy()
    out["ts_code"] = out["ts_code"].astype(str).str.upper()
    out["asset_type"] = "stock"
    out["market"] = "CN_A"
    out["trade_date"] = out["trade_date"].astype(str)
    if "total_mv" in out.columns:
        out["total_mv"] = out["total_mv"].astype(float) * 10000.0
        out["total_mv_yi"] = out["total_mv"] / 1e8
    if "circ_mv" in out.columns:
        out["circ_mv"] = out["circ_mv"].astype(float) * 10000.0
        out["circ_mv_yi"] = out["circ_mv"] / 1e8
    return out.reset_index(drop=True)
