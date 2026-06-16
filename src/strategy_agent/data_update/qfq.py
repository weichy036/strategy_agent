from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from strategy_agent.config import settings


PRICE_COLUMNS = ["open", "high", "low", "close", "pre_close"]


@dataclass(frozen=True)
class QfqBuildResult:
    ok: bool
    requested_codes: list[str]
    built_count: int
    skipped_count: int
    failed_count: int
    latest_built_date: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def build_daily_qfq(
    *,
    daily_dir: Path | None = None,
    adj_factor_dir: Path | None = None,
    output_dir: Path | None = None,
    max_codes: int = 20,
) -> QfqBuildResult:
    raw_dir = daily_dir or settings.raw_root / "daily"
    factor_dir = adj_factor_dir or settings.raw_root / "adj_factor"
    target_dir = output_dir or settings.daily_qfq_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    codes = _candidate_codes(raw_dir, factor_dir, target_dir, max_codes=max_codes)
    built = skipped = failed = 0
    latest_built: str | None = None
    for code in codes:
        try:
            out = build_single_qfq(
                code,
                daily_path=raw_dir / f"{code}.parquet",
                factor_path=factor_dir / f"{code}.parquet",
                output_path=target_dir / f"{code}.parquet",
            )
        except Exception:
            failed += 1
            continue
        if out.empty:
            skipped += 1
            continue
        built += 1
        latest_built = max(latest_built or "", str(out["trade_date"].astype(str).max())) or latest_built
    return QfqBuildResult(
        ok=failed == 0,
        requested_codes=codes,
        built_count=built,
        skipped_count=skipped,
        failed_count=failed,
        latest_built_date=latest_built,
    )


def build_single_qfq(code: str, *, daily_path: Path, factor_path: Path, output_path: Path) -> pd.DataFrame:
    if not daily_path.exists() or not factor_path.exists():
        return pd.DataFrame()
    daily = pd.read_parquet(daily_path)
    factors = pd.read_parquet(factor_path)
    calculated = calc_forward_adjusted_prices(daily, factors)
    if calculated.empty:
        return calculated
    calculated["ts_code"] = code.upper()
    calculated = _merge_existing(output_path, calculated)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    calculated.to_parquet(output_path, index=False)
    return calculated


def calc_forward_adjusted_prices(daily: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    if daily.empty or factors.empty:
        return pd.DataFrame()
    merged = daily.merge(factors[["trade_date", "adj_factor"]], on="trade_date", how="inner")
    if merged.empty:
        return pd.DataFrame()
    merged = merged.copy().sort_values("trade_date").reset_index(drop=True)
    latest_factor = float(merged["adj_factor"].iloc[-1])
    if latest_factor == 0:
        return pd.DataFrame()
    ratio = merged["adj_factor"].astype(float) / latest_factor
    for column in PRICE_COLUMNS:
        if column in merged.columns:
            merged[column] = pd.to_numeric(merged[column], errors="coerce") * ratio
    if "pre_close" in merged.columns and "close" in merged.columns:
        merged["change"] = merged["close"] - merged["pre_close"]
        if "pct_chg" in merged.columns:
            merged["pct_chg"] = (merged["change"] / merged["pre_close"].replace(0, float("nan"))) * 100
    merged["adj_type"] = "qfq"
    return merged


def _candidate_codes(raw_dir: Path, factor_dir: Path, output_dir: Path, *, max_codes: int) -> list[str]:
    codes = sorted(path.stem.upper() for path in raw_dir.glob("*.parquet") if (factor_dir / path.name).exists())
    stale = [code for code in codes if _latest_file_date(raw_dir / f"{code}.parquet") > _latest_file_date(output_dir / f"{code}.parquet")]
    return stale[:max_codes]


def _merge_existing(output_path: Path, calculated: pd.DataFrame) -> pd.DataFrame:
    if not output_path.exists():
        return calculated
    existing = pd.read_parquet(output_path)
    if existing.empty:
        return calculated
    out = pd.concat([existing, calculated], ignore_index=True)
    out["trade_date"] = out["trade_date"].astype(str)
    return out.drop_duplicates(subset=["trade_date"], keep="last").sort_values("trade_date").reset_index(drop=True)


def _latest_file_date(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        frame = pd.read_parquet(path, columns=["trade_date"])
    except Exception:
        return ""
    if frame.empty:
        return ""
    return str(frame["trade_date"].astype(str).max())


__all__ = ["QfqBuildResult", "build_daily_qfq", "build_single_qfq", "calc_forward_adjusted_prices"]
