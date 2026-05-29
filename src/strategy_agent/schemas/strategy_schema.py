from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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
    kind: Literal["indicator_event", "comparison_rule"]
    indicator: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    operator: str | None = None
    value: Any | None = None

    @field_validator("indicator", "operator")
    @classmethod
    def normalize_lowercase(cls, value: str | None) -> str | None:
        return value.lower() if isinstance(value, str) else value


class Signals(BaseModel):
    buy: list[SignalRule] = Field(default_factory=list)
    sell: list[SignalRule] = Field(default_factory=list)


class RankingConfig(BaseModel):
    sort_by: str
    order: Literal["asc", "desc"] = "desc"
    top_n: int
    lookback: Literal["point_in_time", "previous_month_sum", "previous_month_return"] = "point_in_time"

    @field_validator("sort_by")
    @classmethod
    def normalize_sort_field(cls, value: str) -> str:
        aliases = {
            "总市值": "total_mv",
            "市值": "total_mv",
            "总市值最大": "total_mv",
            "流通市值": "circ_mv",
            "成交额": "amount",
            "成交金额": "amount",
            "换手率": "turnover_rate",
            "涨幅": "monthly_return",
            "收益率": "monthly_return",
            "月涨幅": "monthly_return",
            "上月涨幅": "monthly_return",
            "上个月涨幅": "monthly_return",
            "last_month_return": "monthly_return",
            "previous_month_return": "monthly_return",
            "monthly_return": "monthly_return",
        }
        return aliases.get(value, value)


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
    weight_method: str | None = "equal"
    rebalance_frequency: str | None = None
    long_only: bool = True

    @field_validator("weight_method", mode="before")
    @classmethod
    def default_weight_method(cls, value: str | None) -> str:
        return value or "equal"


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
    strategy_type: Literal["signal_trading", "rule_based_timing", "cross_sectional_rotation"]
    universe: Universe
    period: Period
    signals: Signals | None = None
    selection: Selection | None = None
    portfolio: Portfolio | None = None
    execution: Execution
    costs: Costs | None = None
    constraints: Constraints | None = None
    metadata: Metadata | None = None
