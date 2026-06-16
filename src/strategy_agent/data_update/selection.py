from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import pandas as pd

from strategy_agent.config import settings
from strategy_agent.data_access.selection_daily import (
    ensure_selection_daily_frames,
    ensure_selection_monthly_returns,
)


@dataclass(frozen=True)
class SelectionBuildPlan:
    daily_basic_dates: list[str]
    price_dates: list[str]
    existing_selection_dates: list[str]
    missing_daily_dates: list[str]
    months_to_build: list[str]
    latest_price_date: str | None
    blocked_after_price_date_count: int
    unavailable_price_date_count: int

    @property
    def has_work(self) -> bool:
        return bool(self.missing_daily_dates or self.months_to_build)

    def to_dict(self) -> dict:
        return {
            "daily_basic_count": len(self.daily_basic_dates),
            "price_date_count": len(self.price_dates),
            "existing_selection_count": len(self.existing_selection_dates),
            "missing_daily_dates": self.missing_daily_dates,
            "months_to_build": self.months_to_build,
            "latest_price_date": self.latest_price_date,
            "blocked_after_price_date_count": self.blocked_after_price_date_count,
            "unavailable_price_date_count": self.unavailable_price_date_count,
        }


@dataclass(frozen=True)
class SelectionBuildResult:
    ok: bool
    plan: SelectionBuildPlan
    built_daily_count: int
    built_monthly_count: int

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "plan": self.plan.to_dict(),
            "built_daily_count": self.built_daily_count,
            "built_monthly_count": self.built_monthly_count,
        }


def plan_selection_build(
    *,
    daily_basic_dir: Path | None = None,
    daily_qfq_dir: Path | None = None,
    selection_daily_dir: Path | None = None,
    selection_monthly_dir: Path | None = None,
    end_date: str | None = None,
) -> SelectionBuildPlan:
    basic_dates = _date_stems(daily_basic_dir or settings.daily_basic_dir)
    existing_dates = _date_stems(selection_daily_dir or settings.selection_daily_dir)
    price_dates = _complete_trade_dates_in_qfq(daily_qfq_dir or settings.daily_qfq_dir)
    latest_price_date = price_dates[-1] if price_dates else None
    if end_date:
        basic_dates = [item for item in basic_dates if item <= _normalize_date(end_date)]

    if latest_price_date:
        price_date_set = set(price_dates)
        eligible_dates = [item for item in basic_dates if item in price_date_set]
        blocked_count = len([item for item in basic_dates if item > latest_price_date])
    else:
        eligible_dates = []
        blocked_count = len(basic_dates)
    unavailable_count = len(set(basic_dates) - set(eligible_dates)) - blocked_count

    missing_dates = sorted(set(eligible_dates) - set(existing_dates))
    months = _missing_monthly_return_months(
        price_dates,
        selection_monthly_dir or settings.selection_monthly_dir,
    )
    return SelectionBuildPlan(
        daily_basic_dates=basic_dates,
        price_dates=price_dates,
        existing_selection_dates=existing_dates,
        missing_daily_dates=missing_dates,
        months_to_build=months,
        latest_price_date=latest_price_date,
        blocked_after_price_date_count=blocked_count,
        unavailable_price_date_count=max(unavailable_count, 0),
    )


def build_selection_data(
    *,
    execute: bool = True,
    daily_builder=ensure_selection_daily_frames,
    monthly_builder=ensure_selection_monthly_returns,
) -> SelectionBuildResult:
    plan = plan_selection_build()
    if execute and plan.missing_daily_dates:
        daily_builder(plan.missing_daily_dates)
    if execute and plan.months_to_build:
        monthly_builder(plan.months_to_build)
    return SelectionBuildResult(
        ok=True,
        plan=plan,
        built_daily_count=len(plan.missing_daily_dates) if execute else 0,
        built_monthly_count=len(plan.months_to_build) if execute else 0,
    )


def _date_stems(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    return sorted(path.stem for path in directory.glob("*.parquet") if path.stem.isdigit())


def _complete_trade_dates_in_qfq(directory: Path, *, min_coverage_ratio: float = 0.8) -> list[str]:
    counts: dict[str, int] = {}
    if not directory.exists():
        return []
    for path in directory.glob("*.parquet"):
        try:
            frame = pd.read_parquet(path, columns=["trade_date"])
        except Exception:
            continue
        if frame.empty:
            continue
        for trade_date in frame["trade_date"].astype(str).unique().tolist():
            counts[trade_date] = counts.get(trade_date, 0) + 1
    if not counts:
        return []
    threshold = max(1, math.ceil(max(counts.values()) * min_coverage_ratio))
    return sorted(date for date, count in counts.items() if count >= threshold)


def _missing_monthly_return_months(eligible_dates: list[str], directory: Path) -> list[str]:
    months = sorted({date[:6] for date in eligible_dates if len(date) >= 6})
    existing = {path.stem.removesuffix("_monthly_return_sum") for path in directory.glob("*_monthly_return_sum.parquet")}
    return [month for month in months if month not in existing]


def _normalize_date(value: str) -> str:
    return str(value).replace("-", "")[:8]


__all__ = [
    "SelectionBuildPlan",
    "SelectionBuildResult",
    "build_selection_data",
    "plan_selection_build",
]
