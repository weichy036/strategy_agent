from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import time

import pandas as pd

from strategy_agent.config import settings
from strategy_agent.data_update.tushare_policy import TushareRetryPolicy, call_tushare


@dataclass(frozen=True)
class StockSeriesUpdateResult:
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


def update_stock_daily(
    pro,
    *,
    stock_info: pd.DataFrame | None = None,
    daily_dir: Path | None = None,
    qfq_dir: Path | None = None,
    meta_dir: Path | None = None,
    end_date: str | None = None,
    max_codes: int = 20,
    sleep_seconds: float = 0.31,
    retry_policy: TushareRetryPolicy | None = None,
) -> StockSeriesUpdateResult:
    target_dir = daily_dir or settings.raw_root / "daily"
    target_dir.mkdir(parents=True, exist_ok=True)
    candidates = _stale_codes(
        stock_info=stock_info,
        raw_dir=target_dir,
        qfq_dir=qfq_dir or settings.daily_qfq_dir,
        meta_dir=meta_dir,
        end_date=end_date,
        max_codes=max_codes,
    )
    requested: list[str] = []
    failures: list[str] = []
    updated = skipped = empty = failed = 0
    latest_saved: str | None = None
    target_end = _target_end_date(end_date=end_date, meta_dir=meta_dir)

    for code, last_date in candidates:
        start_date = _next_date(last_date)
        if start_date > target_end:
            skipped += 1
            continue
        requested.append(code)
        call = call_tushare(
            lambda code=code, start_date=start_date: pro.daily(ts_code=code, start_date=start_date, end_date=target_end),
            policy=retry_policy,
        )
        if not call.ok:
            failed += 1
            if len(failures) < 3:
                failures.append(f"{code}: {call.error}")
            if _should_stop_after_failures(failed, retry_policy):
                break
            time.sleep(max(sleep_seconds, 1.0))
            continue
        frame = call.frame
        if frame is None or frame.empty:
            empty += 1
            time.sleep(sleep_seconds)
            continue
        saved = _append_partition(target_dir / f"{code}.parquet", frame)
        if saved:
            updated += 1
            latest_saved = max(latest_saved or "", str(frame["trade_date"].astype(str).max())) or latest_saved
        time.sleep(sleep_seconds)
    return StockSeriesUpdateResult(
        ok=failed == 0,
        requested_codes=requested,
        updated_count=updated,
        skipped_count=skipped,
        empty_count=empty,
        failed_count=failed,
        latest_saved_date=latest_saved,
        failure_samples=failures,
    )


def update_adj_factor(
    pro,
    *,
    stock_info: pd.DataFrame | None = None,
    adj_factor_dir: Path | None = None,
    qfq_dir: Path | None = None,
    meta_dir: Path | None = None,
    end_date: str | None = None,
    max_codes: int = 20,
    sleep_seconds: float = 0.31,
    retry_policy: TushareRetryPolicy | None = None,
) -> StockSeriesUpdateResult:
    target_dir = adj_factor_dir or settings.raw_root / "adj_factor"
    target_dir.mkdir(parents=True, exist_ok=True)
    candidates = _stale_codes(
        stock_info=stock_info,
        raw_dir=target_dir,
        qfq_dir=qfq_dir or settings.daily_qfq_dir,
        meta_dir=meta_dir,
        end_date=end_date,
        max_codes=max_codes,
    )
    requested: list[str] = []
    failures: list[str] = []
    updated = skipped = empty = failed = 0
    latest_saved: str | None = None

    for code, _last_date in candidates:
        requested.append(code)
        call = call_tushare(lambda code=code: pro.adj_factor(ts_code=code, trade_date=""), policy=retry_policy)
        if not call.ok:
            failed += 1
            if len(failures) < 3:
                failures.append(f"{code}: {call.error}")
            if _should_stop_after_failures(failed, retry_policy):
                break
            time.sleep(max(sleep_seconds, 1.0))
            continue
        frame = call.frame
        if frame is None or frame.empty:
            empty += 1
            time.sleep(sleep_seconds)
            continue
        frame = frame.copy()
        frame["trade_date"] = frame["trade_date"].astype(str)
        frame = frame.drop_duplicates(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
        frame.to_parquet(target_dir / f"{code}.parquet", index=False)
        updated += 1
        latest_saved = max(latest_saved or "", str(frame["trade_date"].max())) or latest_saved
        time.sleep(sleep_seconds)
    return StockSeriesUpdateResult(
        ok=failed == 0,
        requested_codes=requested,
        updated_count=updated,
        skipped_count=skipped,
        empty_count=empty,
        failed_count=failed,
        latest_saved_date=latest_saved,
        failure_samples=failures,
    )


def _stale_codes(
    *,
    stock_info: pd.DataFrame | None,
    raw_dir: Path,
    qfq_dir: Path,
    meta_dir: Path | None,
    end_date: str | None,
    max_codes: int,
) -> list[tuple[str, str]]:
    target_end = _target_end_date(end_date=end_date, meta_dir=meta_dir)
    codes = _stock_codes(stock_info=stock_info, meta_dir=meta_dir)
    out: list[tuple[str, str]] = []
    for code in codes:
        raw_latest = _latest_file_date(raw_dir / f"{code}.parquet")
        qfq_latest = _latest_file_date(qfq_dir / f"{code}.parquet")
        latest = raw_latest or qfq_latest
        if not latest or latest >= target_end:
            continue
        out.append((code, latest))
        if len(out) >= max_codes:
            break
    return out


def _should_stop_after_failures(failed_count: int, retry_policy: TushareRetryPolicy | None) -> bool:
    policy = retry_policy or TushareRetryPolicy()
    return failed_count >= policy.stop_after_failures


def _stock_codes(*, stock_info: pd.DataFrame | None, meta_dir: Path | None) -> list[str]:
    frame = stock_info
    if frame is None:
        path = (meta_dir or settings.data_root / "meta") / "stock_info.parquet"
        frame = pd.read_parquet(path) if path.exists() else pd.DataFrame()
    if frame.empty or "ts_code" not in frame.columns:
        return sorted(path.stem.upper() for path in settings.daily_qfq_dir.glob("*.parquet"))
    return sorted(frame["ts_code"].astype(str).str.upper().unique().tolist())


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
        old = pd.read_parquet(path)
        out = pd.concat([old, out], ignore_index=True)
    out = out.drop_duplicates(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return True


def _latest_open_date(meta_dir: Path | None) -> str | None:
    path = (meta_dir or settings.data_root / "meta") / "trade_calendar.parquet"
    if not path.exists():
        return None
    frame = pd.read_parquet(path)
    if frame.empty or "cal_date" not in frame.columns:
        return None
    if "is_open" in frame.columns:
        frame = frame[frame["is_open"].astype(int) == 1]
    today = _today_like()
    frame = frame[frame["cal_date"].astype(str) <= today]
    if frame.empty:
        return None
    return str(frame["cal_date"].astype(str).max())


def _latest_daily_basic_date() -> str | None:
    daily_basic_dir = settings.raw_root / "daily_basic"
    dates = [path.stem[:8] for path in daily_basic_dir.glob("*.parquet") if path.stem[:8].isdigit()]
    return max(dates) if dates else None


def _target_end_date(*, end_date: str | None, meta_dir: Path | None) -> str:
    return _normalize_date(end_date) or _latest_daily_basic_date() or _latest_open_date(meta_dir) or _today_like()


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).replace("-", "")[:8]


def _next_date(value: str) -> str:
    return (pd.Timestamp(str(value)) + pd.Timedelta(days=1)).strftime("%Y%m%d")


def _today_like() -> str:
    return pd.Timestamp.today().strftime("%Y%m%d")


__all__ = ["StockSeriesUpdateResult", "update_adj_factor", "update_stock_daily"]
