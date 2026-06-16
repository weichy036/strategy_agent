from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from time import sleep
from typing import Any

import pandas as pd

from strategy_agent.config import settings
from strategy_agent.data_update.tushare_policy import TushareRetryPolicy, call_tushare


@dataclass(frozen=True)
class DailyBasicUpdateResult:
    ok: bool
    target_dir: str
    requested_dates: list[str]
    saved_count: int
    skipped_existing_count: int
    empty_count: int
    failed_count: int
    latest_saved_date: str | None
    failure_samples: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def update_daily_basic(
    pro: Any,
    *,
    trade_calendar: pd.DataFrame | None = None,
    target_dir: Path | None = None,
    meta_dir: Path | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    sleep_seconds: float = 0.31,
    retry_policy: TushareRetryPolicy | None = None,
) -> DailyBasicUpdateResult:
    target = target_dir or settings.daily_basic_dir
    target.mkdir(parents=True, exist_ok=True)
    calendar = trade_calendar if trade_calendar is not None else _load_trade_calendar(meta_dir)
    pending = _pending_open_dates(calendar, target, start_date=start_date, end_date=end_date)

    saved_count = 0
    empty_count = 0
    failed_count = 0
    failures: list[str] = []
    latest_saved_date: str | None = None
    for trade_date in pending:
        call = call_tushare(
            lambda trade_date=trade_date: pro.query("daily_basic", ts_code="", trade_date=trade_date),
            policy=retry_policy,
        )
        if not call.ok:
            failed_count += 1
            if len(failures) < 3:
                failures.append(f"{trade_date}: {call.error}")
            if failed_count >= (retry_policy or TushareRetryPolicy()).stop_after_failures:
                break
            continue
        frame = call.frame
        if frame is None or frame.empty:
            empty_count += 1
        else:
            frame.to_parquet(target / f"{trade_date}.parquet", index=False)
            saved_count += 1
            latest_saved_date = trade_date
        if sleep_seconds > 0:
            sleep(sleep_seconds)

    existing = _existing_dates(target)
    skipped_existing = [d for d in _open_dates(calendar, end_date=end_date) if d in existing]
    return DailyBasicUpdateResult(
        ok=failed_count == 0,
        target_dir=str(target),
        requested_dates=pending,
        saved_count=saved_count,
        skipped_existing_count=len(skipped_existing),
        empty_count=empty_count,
        failed_count=failed_count,
        latest_saved_date=latest_saved_date,
        failure_samples=failures,
    )


def _load_trade_calendar(meta_dir: Path | None = None) -> pd.DataFrame:
    path = (meta_dir or settings.data_root / "meta") / "trade_calendar.parquet"
    if not path.exists():
        raise FileNotFoundError(f"trade calendar not found: {path}")
    return pd.read_parquet(path)


def _pending_open_dates(
    calendar: pd.DataFrame,
    target_dir: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[str]:
    existing = _existing_dates(target_dir)
    open_dates = _open_dates(calendar, end_date=end_date)
    start = _normalize_date(start_date)
    if start is None and existing:
        start = _next_date(max(existing))
    if start is None and open_dates:
        # Avoid accidental full-history pulls when a fresh project has no daily_basic yet.
        start = open_dates[-1]
    return [d for d in open_dates if d not in existing and (start is None or d >= start)]


def _open_dates(calendar: pd.DataFrame, *, end_date: str | None = None) -> list[str]:
    if calendar.empty or "cal_date" not in calendar.columns:
        return []
    frame = calendar.copy()
    frame["cal_date"] = frame["cal_date"].astype(str).str[:8]
    if "is_open" in frame.columns:
        frame = frame[frame["is_open"].astype(int).eq(1)]
    end = _normalize_date(end_date) or date.today().strftime("%Y%m%d")
    return sorted(frame[frame["cal_date"].le(end)]["cal_date"].unique().tolist())


def _existing_dates(target_dir: Path) -> set[str]:
    return {path.stem[:8] for path in target_dir.glob("*.parquet") if len(path.stem) >= 8 and path.stem[:8].isdigit()}


def _next_date(value: str) -> str:
    day = pd.Timestamp(str(value)[:8])
    return (day + pd.Timedelta(days=1)).strftime("%Y%m%d")


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).replace("-", "")[:8]
    if len(normalized) != 8 or not normalized.isdigit():
        return None
    return normalized
