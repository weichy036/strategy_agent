from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

import pandas as pd

from strategy_agent.config import settings


DatasetKind = Literal["date_partitioned", "instrument_partitioned", "period_partitioned"]


@dataclass(frozen=True)
class DatasetStatus:
    name: str
    path: str
    kind: DatasetKind
    exists: bool
    file_count: int
    latest_date: str | None
    lag_days: int | None
    latest_file_mtime: str | None
    stale: bool
    note: str | None = None


@dataclass(frozen=True)
class DataStatusReport:
    as_of_date: str
    stale_after_days: int
    datasets: list[DatasetStatus]

    @property
    def stale_datasets(self) -> list[str]:
        return [item.name for item in self.datasets if item.stale]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["stale_datasets"] = self.stale_datasets
        return data


def collect_data_status(
    *,
    as_of: date | None = None,
    stale_after_days: int = 7,
    raw_root: Path | None = None,
    derived_root: Path | None = None,
) -> DataStatusReport:
    """Return freshness status for local market-data datasets."""
    today = as_of or date.today()
    raw = raw_root or settings.raw_root
    derived = derived_root or settings.derived_root
    datasets = [
        _instrument_partitioned("daily_qfq", derived / "daily_qfq", today, stale_after_days),
        _date_partitioned("daily_basic", raw / "daily_basic", today, stale_after_days),
        _date_partitioned("selection_daily", derived / "selection_daily", today, stale_after_days),
        _instrument_partitioned("fund_daily", raw / "fund_daily", today, stale_after_days),
        _instrument_partitioned("index_daily", raw / "index_daily", today, stale_after_days),
        _period_partitioned("selection_monthly", derived / "selection_monthly", today, stale_after_days),
    ]
    return DataStatusReport(
        as_of_date=today.isoformat(),
        stale_after_days=stale_after_days,
        datasets=datasets,
    )


def main() -> None:
    import json

    print(json.dumps(collect_data_status().to_dict(), ensure_ascii=False, indent=2))


def _date_partitioned(name: str, path: Path, as_of: date, stale_after_days: int) -> DatasetStatus:
    files = sorted(path.glob("*.parquet")) if path.exists() else []
    latest = _latest_yyyymmdd_stem(files)
    return _status(
        name=name,
        path=path,
        kind="date_partitioned",
        files=files,
        latest_date=latest,
        as_of=as_of,
        stale_after_days=stale_after_days,
    )


def _period_partitioned(name: str, path: Path, as_of: date, stale_after_days: int) -> DatasetStatus:
    files = sorted(path.glob("*.parquet")) if path.exists() else []
    latest = _latest_period_stem(files)
    return _status(
        name=name,
        path=path,
        kind="period_partitioned",
        files=files,
        latest_date=latest,
        as_of=as_of,
        stale_after_days=stale_after_days,
        note="period data uses the first six digits in the file name as YYYYMM.",
    )


def _instrument_partitioned(name: str, path: Path, as_of: date, stale_after_days: int) -> DatasetStatus:
    files = sorted(path.glob("*.parquet")) if path.exists() else []
    latest = _latest_trade_date(files)
    return _status(
        name=name,
        path=path,
        kind="instrument_partitioned",
        files=files,
        latest_date=latest,
        as_of=as_of,
        stale_after_days=stale_after_days,
    )


def _status(
    *,
    name: str,
    path: Path,
    kind: DatasetKind,
    files: list[Path],
    latest_date: str | None,
    as_of: date,
    stale_after_days: int,
    note: str | None = None,
) -> DatasetStatus:
    lag_days = _lag_days(latest_date, as_of)
    return DatasetStatus(
        name=name,
        path=str(path),
        kind=kind,
        exists=path.exists(),
        file_count=len(files),
        latest_date=latest_date,
        lag_days=lag_days,
        latest_file_mtime=_latest_mtime(files),
        stale=lag_days is None or lag_days > stale_after_days,
        note=note,
    )


def _latest_trade_date(files: list[Path]) -> str | None:
    latest: str | None = None
    for path in files:
        try:
            frame = pd.read_parquet(path, columns=["trade_date"])
        except Exception:  # noqa: BLE001
            continue
        if frame.empty:
            continue
        value = str(frame["trade_date"].max())[:8]
        if _is_yyyymmdd(value) and (latest is None or value > latest):
            latest = value
    return latest


def _latest_yyyymmdd_stem(files: list[Path]) -> str | None:
    dates = [path.stem[:8] for path in files if _is_yyyymmdd(path.stem[:8])]
    return max(dates) if dates else None


def _latest_period_stem(files: list[Path]) -> str | None:
    periods = [path.stem[:6] for path in files if len(path.stem) >= 6 and path.stem[:6].isdigit()]
    if not periods:
        return None
    period = max(periods)
    return f"{period}01"


def _latest_mtime(files: list[Path]) -> str | None:
    if not files:
        return None
    ts = max(path.stat().st_mtime for path in files)
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def _lag_days(latest_date: str | None, as_of: date) -> int | None:
    if not latest_date or not _is_yyyymmdd(latest_date):
        return None
    value = datetime.strptime(latest_date, "%Y%m%d").date()
    return (as_of - value).days


def _is_yyyymmdd(value: str) -> bool:
    if len(value) != 8 or not value.isdigit():
        return False
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    main()
