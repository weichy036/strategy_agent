from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RequiredDataset(BaseModel):
    dataset: Literal["fund_daily", "index_daily", "daily_qfq", "daily_basic", "selection_daily", "adj_factor"]
    symbols: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    frequency: Literal["1d"] = "1d"
    fields: list[str] = Field(default_factory=list)
    local_path_hint: str | None = None
    fallback_api: str | None = None


class LocalCoverage(BaseModel):
    dataset: str
    symbol: str | None = None
    exists: bool
    start_date: str | None = None
    end_date: str | None = None
    row_count: int = 0
    missing_fields: list[str] = Field(default_factory=list)


class DataFetchPlan(BaseModel):
    task_type: str
    api_name: str
    symbols: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    fields: list[str] = Field(default_factory=list)
    target_path: str
    reason: str


class FactorSpec(BaseModel):
    name: str
    display_name: str
    status: Literal["ready", "needs_build", "needs_fetch", "unsupported"] = "ready"
    source_type: Literal["raw_field", "derived", "external_fetch", "unsupported"]
    dataset: str
    base_datasets: list[str] = Field(default_factory=list)
    base_fields: list[str] = Field(default_factory=list)
    compute_method: str | None = None
    lookback: str | None = None
    rationale: str = ""


class FactorBuildPlan(BaseModel):
    factor_name: str
    builder: str
    target_dataset: str
    base_datasets: list[str] = Field(default_factory=list)
    base_fields: list[str] = Field(default_factory=list)
    reason: str


class DataAvailabilityReport(BaseModel):
    is_required: bool
    is_ready: bool
    can_continue_backtest: bool | None = None
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_factors: list[FactorSpec] = Field(default_factory=list)
    required_datasets: list[RequiredDataset] = Field(default_factory=list)
    local_coverage: list[LocalCoverage] = Field(default_factory=list)
    factor_build_plan: list[FactorBuildPlan] = Field(default_factory=list)
    fetch_plan: list[DataFetchPlan] = Field(default_factory=list)
    schema_patch: dict[str, str] = Field(default_factory=dict)
    rationale: str
