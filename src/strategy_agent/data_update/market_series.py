from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import time
from typing import Callable

import pandas as pd

from strategy_agent.config import settings
from strategy_agent.data_update.tushare_policy import TushareRetryPolicy, call_tushare


@dataclass(frozen=True)
class MarketSeriesUpdateResult:
    ok: bool
    requested_codes: list[str]
    updated_count: int
    skipped_count: int
    empty_count: int
    failed_count: int
    latest_saved_date: str | None
    failure_samples: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def update_fund_daily(
    pro,
    *,
    fund_info: pd.DataFrame | None = None,
    target_dir: Path | None = None,
    meta_dir: Path | None = None,
    end_date: str | None = None,
    max_codes: int = 20,
    sleep_seconds: float = 0.31,
    retry_policy: TushareRetryPolicy | None = None,
) -> MarketSeriesUpdateResult:
    return _update_series(
        lambda code, start, end: pro.fund_daily(ts_code=code, start_date=start, end_date=end),
        codes=_fund_codes(fund_info=fund_info, target_dir=target_dir, meta_dir=meta_dir),
        target_dir=target_dir or settings.fund_daily_dir,
        end_date=end_date,
        max_codes=max_codes,
        sleep_seconds=sleep_seconds,
        retry_policy=retry_policy,
    )


def update_index_daily(
    pro,
    *,
    index_codes: list[str] | None = None,
    target_dir: Path | None = None,
    end_date: str | None = None,
    max_codes: int = 20,
    sleep_seconds: float = 0.31,
    retry_policy: TushareRetryPolicy | None = None,
) -> MarketSeriesUpdateResult:
    return _update_series(
        lambda code, start, end: pro.index_daily(ts_code=code, start_date=start, end_date=end),
        codes=index_codes or _existing_codes(target_dir or settings.index_daily_dir),
        target_dir=target_dir or settings.index_daily_dir,
        end_date=end_date,
        max_codes=max_codes,
        sleep_seconds=sleep_seconds,
        retry_policy=retry_policy,
    )


def _update_series(
    request: Callable[[str, str, str], pd.DataFrame | None],
    *,
    codes: list[str],
    target_dir: Path,
    end_date: str | None,
    max_codes: int,
    sleep_seconds: float,
    retry_policy: TushareRetryPolicy | None,
) -> MarketSeriesUpdateResult:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_end = _target_end_date(end_date=end_date)
    requested: list[str] = []
    failures: list[str] = []
    updated = skipped = empty = failed = 0
    latest_saved: str | None = None

    for code in _stale_codes(codes, target_dir=target_dir, target_end=target_end, max_codes=max_codes):
        last_date = _latest_file_date(target_dir / f"{code}.parquet")
        start_date = _next_date(last_date)
        if start_date > target_end:
            skipped += 1
            continue
        requested.append(code)
        call = call_tushare(lambda code=code, start=start_date: request(code, start, target_end), policy=retry_policy)
        if not call.ok:
            failed += 1
            if len(failures) < 3:
                failures.append(f"{code}: {call.error}")
            if failed >= (retry_policy or TushareRetryPolicy()).stop_after_failures:
                break
            time.sleep(max(sleep_seconds, 1.0))
            continue
        frame = call.frame
        if frame is None or frame.empty:
            empty += 1
            time.sleep(sleep_seconds)
            continue
        if _append_partition(target_dir / f"{code}.parquet", frame):
            updated += 1
            latest_saved = max(latest_saved or "", str(frame["trade_date"].astype(str).max())) or latest_saved
        time.sleep(sleep_seconds)

    return MarketSeriesUpdateResult(
        ok=failed == 0,
        requested_codes=requested,
        updated_count=updated,
        skipped_count=skipped,
        empty_count=empty,
        failed_count=failed,
        latest_saved_date=latest_saved,
        failure_samples=failures,
    )


def _fund_codes(*, fund_info: pd.DataFrame | None, target_dir: Path | None, meta_dir: Path | None) -> list[str]:
    existing = _existing_codes(target_dir or settings.fund_daily_dir)
    frame = fund_info
    if frame is None:
        path = (meta_dir or settings.data_root / "meta") / "fund_info.parquet"
        frame = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    if frame is not None and not frame.empty and "ts_code" in frame.columns:
        discovered = sorted(frame["ts_code"].astype(str).str.upper().unique().tolist())
        return existing + [code for code in discovered if code not in set(existing)]
    return existing


def _existing_codes(target_dir: Path) -> list[str]:
    return sorted(path.stem.upper() for path in target_dir.glob("*.parquet")) if target_dir.exists() else []


def _stale_codes(codes: list[str], *, target_dir: Path, target_end: str, max_codes: int) -> list[str]:
    out: list[str] = []
    for code in codes:
        latest = _latest_file_date(target_dir / f"{code}.parquet")
        if not latest or latest < target_end:
            out.append(code)
        if len(out) >= max_codes:
            break
    return out


def _latest_file_date(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path, columns=["trade_date"])
    except Exception:
        return None
    if frame.empty:
        return None
    return str(frame["trade_date"].astype(str).max())


def _append_partition(path: Path, frame: pd.DataFrame) -> bool:
    out = frame.copy()
    if "trade_date" not in out.columns or out.empty:
        return False
    out["trade_date"] = out["trade_date"].astype(str)
    if path.exists():
        out = pd.concat([pd.read_parquet(path), out], ignore_index=True)
    out = out.drop_duplicates(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return True


def _target_end_date(*, end_date: str | None) -> str:
    if end_date:
        return end_date
    path = settings.raw_root / "daily_basic"
    dates = [item.stem[:8] for item in path.glob("*.parquet") if len(item.stem) >= 8 and item.stem[:8].isdigit()]
    return max(dates) if dates else pd.Timestamp.today().strftime("%Y%m%d")


def _next_date(value: str | None) -> str:
    if not value:
        return "20150101"
    return (pd.to_datetime(value) + pd.Timedelta(days=1)).strftime("%Y%m%d")


__all__ = ["MarketSeriesUpdateResult", "update_fund_daily", "update_index_daily"]
