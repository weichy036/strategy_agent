from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from strategy_agent.config import settings
from strategy_agent.data_access.selection_daily import (
    SELECTION_DAILY_FIELDS,
    SELECTION_DERIVED_FIELDS,
    load_selection_monthly_return,
    resolve_selection_trade_date,
)
from strategy_agent.data_access.storage import daily_basic_path, daily_qfq_path, fund_daily_path, index_daily_path, selection_daily_path
from strategy_agent.domain.instruments import resolve_instrument
from strategy_agent.schemas.data_research import (
    DataAvailabilityReport,
    FactorBuildPlan,
    FactorSpec,
    DataFetchPlan,
    LocalCoverage,
    RequiredDataset,
)
from strategy_agent.services.factor_catalog import canonical_factor_name, factor_definition


PRICE_FIELDS = ["trade_date", "open", "high", "low", "close"]
SELECTION_BASE_FIELDS = ["ts_code", "trade_date"]


def inspect_strategy_data(strategy_schema: dict[str, Any] | None) -> DataAvailabilityReport:
    if not strategy_schema:
        return DataAvailabilityReport(
            is_required=True,
            is_ready=False,
            blocking_issues=["strategy_schema_missing"],
            rationale="缺少策略结构，无法判断数据需求。",
        )

    required_factors = required_factors_for_strategy(strategy_schema)
    schema_patch = schema_patch_for_strategy(strategy_schema)
    required = required_datasets_for_strategy(strategy_schema)
    coverage = [_inspect_dataset(item) for item in required]
    blocking = _blocking_issues(coverage)
    fetch_plan = [_fetch_plan(item, result) for item, result in zip(required, coverage) if not _coverage_ready(result)]
    factor_build_plan = _factor_build_plan(required_factors, coverage)

    return DataAvailabilityReport(
        is_required=True,
        is_ready=not blocking,
        can_continue_backtest=not blocking,
        blocking_issues=blocking,
        warnings=_warnings(strategy_schema),
        required_factors=required_factors,
        required_datasets=required,
        local_coverage=coverage,
        factor_build_plan=factor_build_plan,
        fetch_plan=fetch_plan,
        schema_patch=schema_patch,
        rationale="本地数据足以支撑回测。" if not blocking else "本地数据存在缺口，需要先补齐数据。",
    )


def required_factors_for_strategy(strategy_schema: dict[str, Any]) -> list[FactorSpec]:
    if strategy_schema.get("strategy_type") != "cross_sectional_rotation":
        return []
    field = _raw_ranking_field(strategy_schema)
    factor = factor_definition(field)
    if factor:
        return [factor.to_spec(status="ready")]
    if not field:
        return []
    return [
        FactorSpec(
            name=str(field),
            display_name=str(field),
            status="unsupported",
            source_type="unsupported",
            dataset="unknown",
            rationale="因子目录暂不支持该字段。",
        )
    ]


def required_datasets_for_strategy(strategy_schema: dict[str, Any]) -> list[RequiredDataset]:
    strategy_type = strategy_schema.get("strategy_type")
    period = strategy_schema.get("period") or {}
    start_date = _date_text(period.get("start"))
    end_date = _date_text(period.get("end")) or "latest"

    if strategy_type == "cross_sectional_rotation":
        ranking_field = _ranking_field(strategy_schema)
        return [
            RequiredDataset(
                dataset="selection_daily",
                start_date=start_date,
                end_date=end_date,
                fields=SELECTION_BASE_FIELDS + ([ranking_field] if ranking_field else []),
                local_path_hint=str(selection_daily_path(resolve_selection_trade_date(end_date) or "latest")),
                fallback_api="daily+daily_basic",
            )
        ]

    symbols = [_normalize_symbol(str(item)) for item in ((strategy_schema.get("universe") or {}).get("symbols") or [])]
    if not symbols:
        return []
    symbol = symbols[0]
    dataset = _price_dataset(symbol)
    return [
        RequiredDataset(
            dataset=dataset,
            symbols=[symbol],
            start_date=start_date,
            end_date=end_date,
            fields=PRICE_FIELDS,
            local_path_hint=str(_dataset_path(dataset, symbol)),
            fallback_api=_fallback_api(dataset),
        )
    ]


def _inspect_dataset(item: RequiredDataset) -> LocalCoverage:
    if item.dataset == "daily_basic":
        return _inspect_daily_basic(item)
    if item.dataset == "selection_daily":
        return _inspect_selection_daily(item)
    symbol = item.symbols[0] if item.symbols else None
    path = _dataset_path(item.dataset, symbol or "")
    return _inspect_parquet(path, item.dataset, symbol, item.fields)


def _inspect_daily_basic(item: RequiredDataset) -> LocalCoverage:
    path = _latest_daily_basic_path()
    if path is None:
        return LocalCoverage(dataset="daily_basic", symbol=None, exists=False, missing_fields=item.fields)
    return _inspect_parquet(path, "daily_basic", None, item.fields)


def _inspect_selection_daily(item: RequiredDataset) -> LocalCoverage:
    date = resolve_selection_trade_date(item.end_date or "latest")
    if not date:
        return LocalCoverage(dataset="selection_daily", symbol=None, exists=False, missing_fields=item.fields)
    path = selection_daily_path(date)
    if path.exists():
        coverage = _inspect_parquet(path, "selection_daily", None, [field for field in item.fields if field not in SELECTION_DERIVED_FIELDS])
        derived_missing = _missing_derived_selection_fields(item, date)
        coverage.missing_fields.extend(derived_missing)
        return coverage
    missing = [field for field in item.fields if field not in SELECTION_DAILY_FIELDS and field not in SELECTION_DERIVED_FIELDS]
    missing.extend(_missing_derived_selection_fields(item, date))
    return LocalCoverage(
        dataset="selection_daily",
        symbol=None,
        exists=not missing,
        start_date=date,
        end_date=date,
        row_count=1 if not missing else 0,
        missing_fields=missing,
    )


def _missing_derived_selection_fields(item: RequiredDataset, trade_date: str) -> list[str]:
    missing: list[str] = []
    if "monthly_return" in item.fields:
        frame = load_selection_monthly_return(_previous_month(trade_date))
        if frame.empty or "monthly_return" not in frame.columns:
            missing.append("monthly_return")
    return missing


def _inspect_parquet(path: Path, dataset: str, symbol: str | None, fields: list[str]) -> LocalCoverage:
    if not path.exists():
        return LocalCoverage(dataset=dataset, symbol=symbol, exists=False, missing_fields=fields)
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return LocalCoverage(dataset=dataset, symbol=symbol, exists=False, missing_fields=fields)
    missing = [field for field in fields if field not in frame.columns]
    dates = frame["trade_date"].astype(str) if "trade_date" in frame.columns and not frame.empty else None
    return LocalCoverage(
        dataset=dataset,
        symbol=symbol,
        exists=True,
        start_date=str(dates.min()) if dates is not None else None,
        end_date=str(dates.max()) if dates is not None else None,
        row_count=len(frame),
        missing_fields=missing,
    )


def _blocking_issues(coverage: list[LocalCoverage]) -> list[str]:
    issues: list[str] = []
    for item in coverage:
        label = item.dataset if item.symbol is None else f"{item.dataset}:{item.symbol}"
        if not item.exists:
            issues.append(f"{label}:missing")
        elif item.row_count <= 0:
            issues.append(f"{label}:empty")
        elif item.missing_fields:
            issues.append(f"{label}:missing_fields:{','.join(item.missing_fields)}")
    return issues


def _coverage_ready(item: LocalCoverage) -> bool:
    return item.exists and item.row_count > 0 and not item.missing_fields


def _fetch_plan(item: RequiredDataset, coverage: LocalCoverage) -> DataFetchPlan:
    return DataFetchPlan(
        task_type=item.dataset,
        api_name=item.fallback_api or item.dataset,
        symbols=item.symbols,
        start_date=item.start_date,
        end_date=item.end_date,
        fields=item.fields,
        target_path=item.local_path_hint or "",
        reason=";".join(_blocking_issues([coverage])) or "backtest_missing_local_data",
    )


def _factor_build_plan(factors: list[FactorSpec], coverage: list[LocalCoverage]) -> list[FactorBuildPlan]:
    if not _blocking_issues(coverage):
        return []
    plans: list[FactorBuildPlan] = []
    missing_fields = {field for item in coverage for field in item.missing_fields}
    for spec in factors:
        definition = factor_definition(spec.name)
        if not definition or definition.source_type != "derived" or spec.name not in missing_fields or not definition.builder:
            continue
        plans.append(
            FactorBuildPlan(
                factor_name=definition.name,
                builder=definition.builder,
                target_dataset=definition.dataset,
                base_datasets=list(definition.base_datasets),
                base_fields=list(definition.base_fields),
                reason=f"{definition.name}:missing_derived_factor",
            )
        )
    return plans


def _warnings(strategy_schema: dict[str, Any]) -> list[str]:
    period = strategy_schema.get("period") or {}
    warnings: list[str] = []
    if not period.get("start") or not period.get("end"):
        warnings.append("period.start_or_end_uses_local_default")
    return warnings


def _price_dataset(symbol: str) -> str:
    if symbol.startswith(("5", "1")):
        return "fund_daily"
    if symbol.startswith("000") and symbol.endswith(".SH"):
        return "index_daily"
    return "daily_qfq"


def _normalize_symbol(symbol: str) -> str:
    resolved = resolve_instrument(symbol)
    instrument = resolved.get("instrument") if resolved.get("resolved") else None
    if isinstance(instrument, dict) and instrument.get("ts_code"):
        return str(instrument["ts_code"]).upper()
    return symbol.upper()


def _dataset_path(dataset: str, symbol: str) -> Path:
    if dataset == "fund_daily":
        return fund_daily_path(symbol)
    if dataset == "index_daily":
        return index_daily_path(symbol)
    if dataset == "daily_qfq":
        return daily_qfq_path(symbol)
    if dataset == "daily_basic":
        return _latest_daily_basic_path() or daily_basic_path("latest")
    if dataset == "selection_daily":
        return selection_daily_path(resolve_selection_trade_date("latest") or "latest")
    return settings.raw_root / dataset / f"{symbol}.parquet"


def _fallback_api(dataset: str) -> str:
    return {"daily_qfq": "daily+adj_factor"}.get(dataset, dataset)


def _ranking_field(strategy_schema: dict[str, Any]) -> str | None:
    return canonical_factor_name(_raw_ranking_field(strategy_schema) or "total_mv")


def _raw_ranking_field(strategy_schema: dict[str, Any]) -> str | None:
    selection = strategy_schema.get("selection") or {}
    ranking = selection.get("ranking") or {}
    sort_by = ranking.get("sort_by")
    return str(sort_by) if sort_by else None


def schema_patch_for_strategy(strategy_schema: dict[str, Any]) -> dict[str, str]:
    raw = _raw_ranking_field(strategy_schema)
    canonical = canonical_factor_name(raw)
    if raw and canonical and raw != canonical:
        patch = {"selection.ranking.sort_by": canonical}
        if canonical == "monthly_return":
            patch["selection.ranking.lookback"] = "previous_month_return"
        return patch
    return {}


def _previous_month(trade_date: str) -> str:
    year = int(trade_date[:4])
    month = int(trade_date[4:6])
    if month == 1:
        return f"{year - 1}12"
    return f"{year}{month - 1:02d}"


def _latest_daily_basic_path() -> Path | None:
    files = sorted(settings.daily_basic_dir.glob("*.parquet"), reverse=True)
    return files[0] if files else None


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("-", "")
    return None if text.lower() in {"", "none", "null"} else text
