from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Universe(BaseModel):
    type: Literal["instrument", "equity_universe"]
    symbols: list[str] = Field(default_factory=list)
    scope: str | None = None
    filters: list[str] = Field(default_factory=list)


class Period(BaseModel):
    frequency: Literal["1d"] = "1d"
    start: str | None = None
    end: str | None = None


class SignalRule(BaseModel):
    kind: str
    indicator: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    operator: str | None = None
    value: Any | None = None


class Signals(BaseModel):
    buy: list[SignalRule] = Field(default_factory=list)
    sell: list[SignalRule] = Field(default_factory=list)


class RankingConfig(BaseModel):
    sort_by: str
    order: Literal["asc", "desc"] = "desc"
    top_n: int


class HoldPeriod(BaseModel):
    type: str
    frequency: str | None = None
    days: int | None = None


class FilterRule(BaseModel):
    field: str
    operator: str
    value: Any


class Selection(BaseModel):
    filters: list[FilterRule] = Field(default_factory=list)
    ranking: RankingConfig | None = None
    hold_period: HoldPeriod | None = None


class Portfolio(BaseModel):
    position_count: int | None = None
    weight_method: str | None = None
    rebalance_frequency: str | None = None
    long_only: bool = True


class Execution(BaseModel):
    buy_price: str = "next_open"
    sell_price: str = "next_open"
    trade_timing: str = "next_bar"
    rebalance_trigger: str = "calendar"


class Costs(BaseModel):
    commission_bps: int | float = 3
    slippage_bps: int | float = 5


class Constraints(BaseModel):
    tradability_filters: list[str] = Field(default_factory=list)
    allow_short: bool = False


class Metadata(BaseModel):
    source_query: str | None = None
    defaulted_fields: list[str] = Field(default_factory=list)


class StrategySchema(BaseModel):
    schema_version: Literal["v1"] = "v1"
    strategy_id: str | None = None
    name: str | None = None
    market: Literal["CN"] = "CN"
    strategy_type: str
    universe: Universe
    period: Period
    signals: Signals | None = None
    selection: Selection | None = None
    portfolio: Portfolio | None = None
    execution: Execution
    costs: Costs | None = None
    constraints: Constraints | None = None
    metadata: Metadata | None = None
