from __future__ import annotations

from pathlib import Path

import pandas as pd

from strategy_agent.config import settings
from strategy_agent.data_access.normalize import load_daily_basic_frame
from strategy_agent.data_access.storage import selection_daily_path, selection_monthly_path


SELECTION_DAILY_FIELDS = [
    "ts_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "vol",
    "amount",
    "pct_chg",
    "turnover_rate",
    "turnover_rate_f",
    "total_mv",
    "circ_mv",
    "pe",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "total_share",
    "float_share",
    "free_share",
]
SELECTION_DERIVED_FIELDS = ["monthly_return"]

PRICE_FIELDS = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount", "pct_chg"]
BASIC_FIELDS = [
    "ts_code",
    "trade_date",
    "turnover_rate",
    "turnover_rate_f",
    "total_mv",
    "circ_mv",
    "pe",
    "pe_ttm",
    "pb",
    "ps_ttm",
    "total_share",
    "float_share",
    "free_share",
]


def load_selection_daily_frame(trade_date: str = "latest", *, build_if_missing: bool = True) -> pd.DataFrame:
    target_date = resolve_selection_trade_date(trade_date)
    if not target_date:
        return pd.DataFrame(columns=SELECTION_DAILY_FIELDS)

    path = selection_daily_path(target_date)
    if path.exists():
        return _normalize(pd.read_parquet(path))
    if not build_if_missing:
        return pd.DataFrame(columns=SELECTION_DAILY_FIELDS)
    return build_selection_daily_frame(target_date, persist=True)


def build_selection_daily_frame(trade_date: str, *, persist: bool = True) -> pd.DataFrame:
    target_date = resolve_selection_trade_date(trade_date)
    if not target_date:
        return pd.DataFrame(columns=SELECTION_DAILY_FIELDS)

    prices = _price_cross_section(target_date)
    basics = _basic_cross_section(target_date)
    if prices.empty and basics.empty:
        return pd.DataFrame(columns=SELECTION_DAILY_FIELDS)
    if prices.empty:
        merged = basics
    elif basics.empty:
        merged = prices
    else:
        merged = prices.merge(basics.drop(columns=["trade_date"], errors="ignore"), on="ts_code", how="left")

    merged["trade_date"] = target_date
    merged = _normalize(merged)
    if persist and not merged.empty:
        path = selection_daily_path(target_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_parquet(path, index=False)
    return merged


def ensure_selection_daily_frames(trade_dates: list[str]) -> None:
    target_dates = sorted({date for date in (resolve_selection_trade_date(item) for item in trade_dates) if date})
    missing_dates = [date for date in target_dates if not selection_daily_path(date).exists()]
    if not missing_dates:
        return

    buckets: dict[str, list[dict]] = {date: [] for date in missing_dates}
    missing_set = set(missing_dates)
    for path in settings.daily_qfq_dir.glob("*.parquet"):
        try:
            frame = pd.read_parquet(path, columns=PRICE_FIELDS)
        except Exception:
            continue
        if frame.empty:
            continue
        frame["trade_date"] = frame["trade_date"].astype(str)
        frame = frame[frame["trade_date"].isin(missing_set)]
        if frame.empty:
            continue
        frame["ts_code"] = frame.get("ts_code", path.stem).astype(str).str.upper()
        for row in frame.to_dict("records"):
            buckets[str(row["trade_date"])].append(row)

    for date, rows in buckets.items():
        prices = pd.DataFrame(rows, columns=PRICE_FIELDS)
        basics = _basic_cross_section(date)
        if prices.empty and basics.empty:
            continue
        merged = basics if prices.empty else prices if basics.empty else prices.merge(
            basics.drop(columns=["trade_date"], errors="ignore"),
            on="ts_code",
            how="left",
        )
        merged["trade_date"] = date
        merged = _normalize(merged)
        if not merged.empty:
            path = selection_daily_path(date)
            path.parent.mkdir(parents=True, exist_ok=True)
            merged.to_parquet(path, index=False)


def load_selection_monthly_sum(month: str, field: str) -> pd.DataFrame:
    normalized_month = str(month).replace("-", "")[:6]
    path = selection_monthly_path(normalized_month, field)
    if path.exists():
        return pd.read_parquet(path)

    rows = []
    columns = ["ts_code", "trade_date", field]
    for source in settings.daily_qfq_dir.glob("*.parquet"):
        try:
            frame = pd.read_parquet(source, columns=columns)
        except Exception:
            continue
        if frame.empty:
            continue
        frame["trade_date"] = frame["trade_date"].astype(str)
        frame = frame[frame["trade_date"].str.startswith(normalized_month)]
        if frame.empty:
            continue
        frame["ts_code"] = frame.get("ts_code", source.stem).astype(str).str.upper()
        rows.append(frame[["ts_code", field]])

    if not rows:
        return pd.DataFrame(columns=["ts_code", field])

    out = pd.concat(rows, ignore_index=True)
    out[field] = pd.to_numeric(out[field], errors="coerce")
    out = out.dropna(subset=[field]).groupby("ts_code", as_index=False)[field].sum()
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return out


def load_selection_monthly_return(month: str) -> pd.DataFrame:
    normalized_month = str(month).replace("-", "")[:6]
    path = selection_monthly_path(normalized_month, "monthly_return")
    if path.exists():
        return pd.read_parquet(path)
    ensure_selection_monthly_returns([normalized_month])
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame(columns=["ts_code", "monthly_return"])


def ensure_selection_monthly_returns(months: list[str]) -> None:
    target_months = sorted({str(month).replace("-", "")[:6] for month in months if month})
    missing_months = [month for month in target_months if not selection_monthly_path(month, "monthly_return").exists()]
    if not missing_months:
        return

    missing_set = set(missing_months)
    buckets: dict[str, list[dict]] = {month: [] for month in missing_months}
    for source in settings.daily_qfq_dir.glob("*.parquet"):
        try:
            frame = pd.read_parquet(source, columns=["trade_date", "close"])
        except Exception:
            continue
        if frame.empty:
            continue
        frame = frame.copy()
        frame["trade_date"] = frame["trade_date"].astype(str)
        frame["month"] = frame["trade_date"].str[:6]
        frame = frame[frame["month"].isin(missing_set)]
        if frame.empty:
            continue
        for month, group in frame.sort_values("trade_date").groupby("month"):
            if len(group) < 2:
                continue
            first_close = float(group.iloc[0]["close"])
            last_close = float(group.iloc[-1]["close"])
            if first_close <= 0:
                continue
            buckets[str(month)].append({"ts_code": source.stem.upper(), "monthly_return": last_close / first_close - 1.0})

    for month, rows in buckets.items():
        out = pd.DataFrame(rows, columns=["ts_code", "monthly_return"])
        if out.empty:
            continue
        path = selection_monthly_path(month, "monthly_return")
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(path, index=False)


def resolve_selection_trade_date(trade_date: str = "latest") -> str | None:
    target = str(trade_date or "latest").replace("-", "")
    if target.lower() == "latest":
        candidates = _all_trade_dates()
        return candidates[-1] if candidates else None
    candidates = [date for date in _all_trade_dates() if date <= target]
    return candidates[-1] if candidates else None


def _price_cross_section(trade_date: str) -> pd.DataFrame:
    rows = []
    for path in settings.daily_qfq_dir.glob("*.parquet"):
        row = _price_row(path, trade_date)
        if row is not None:
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=PRICE_FIELDS)
    return pd.DataFrame(rows)


def _price_row(path: Path, trade_date: str) -> dict | None:
    try:
        frame = pd.read_parquet(path, columns=PRICE_FIELDS)
    except Exception:
        return None
    if frame.empty:
        return None
    frame = frame[frame["trade_date"].astype(str) == trade_date]
    if frame.empty:
        return None
    row = frame.iloc[-1].to_dict()
    row["ts_code"] = str(row.get("ts_code") or path.stem).upper()
    return row


def _basic_cross_section(trade_date: str) -> pd.DataFrame:
    frame = load_daily_basic_frame(trade_date)
    if frame.empty:
        return pd.DataFrame(columns=BASIC_FIELDS)
    fields = [field for field in BASIC_FIELDS if field in frame.columns]
    return frame[fields].copy()


def _all_trade_dates() -> list[str]:
    dates: set[str] = set()
    dates.update(path.stem for path in settings.selection_daily_dir.glob("*.parquet"))
    dates.update(path.stem for path in settings.daily_basic_dir.glob("*.parquet"))
    return sorted(dates)


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for field in SELECTION_DAILY_FIELDS:
        if field not in out.columns:
            out[field] = pd.NA
    out["ts_code"] = out["ts_code"].astype(str).str.upper()
    out["trade_date"] = out["trade_date"].astype(str)
    return out[SELECTION_DAILY_FIELDS].reset_index(drop=True)


__all__ = [
    "SELECTION_DERIVED_FIELDS",
    "SELECTION_DAILY_FIELDS",
    "build_selection_daily_frame",
    "ensure_selection_daily_frames",
    "ensure_selection_monthly_returns",
    "load_selection_daily_frame",
    "load_selection_monthly_sum",
    "load_selection_monthly_return",
    "resolve_selection_trade_date",
]
