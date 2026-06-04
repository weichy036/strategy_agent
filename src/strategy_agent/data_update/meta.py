from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from strategy_agent.config import settings


@dataclass(frozen=True)
class MetaRefreshResult:
    ok: bool
    meta_dir: str
    stock_count: int
    trade_calendar_count: int
    fund_count: int
    skipped_fund_info: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def refresh_meta(pro: Any, *, meta_dir: Path | None = None) -> MetaRefreshResult:
    target = meta_dir or settings.data_root / "meta"
    target.mkdir(parents=True, exist_ok=True)

    stock_info = pro.stock_basic(
        exchange="",
        list_status="L",
        fields="ts_code,symbol,name,area,industry,list_date,list_status",
    )
    stock_info = _sorted_frame(stock_info, "ts_code")
    stock_info.to_parquet(target / "stock_info.parquet", index=False)

    trade_cal = pro.trade_cal(exchange="", start_date="20150101", end_date="20301231")
    trade_cal = _sorted_frame(trade_cal, "cal_date")
    trade_cal.to_parquet(target / "trade_calendar.parquet", index=False)

    fund_count = 0
    skipped_fund_info = False
    try:
        fund_info = pro.fund_basic(market="E")
    except Exception:  # noqa: BLE001
        fund_info = pd.DataFrame()
        skipped_fund_info = True
    if fund_info is not None and not fund_info.empty:
        fund_info = _sorted_frame(fund_info, "ts_code")
        fund_info.to_parquet(target / "fund_info.parquet", index=False)
        fund_count = len(fund_info)
    else:
        skipped_fund_info = True

    return MetaRefreshResult(
        ok=True,
        meta_dir=str(target),
        stock_count=len(stock_info),
        trade_calendar_count=len(trade_cal),
        fund_count=fund_count,
        skipped_fund_info=skipped_fund_info,
    )


def _sorted_frame(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    if column not in frame.columns:
        return frame.reset_index(drop=True)
    return frame.sort_values(column).reset_index(drop=True)
