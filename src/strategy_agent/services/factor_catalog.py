from __future__ import annotations

from dataclasses import dataclass, field

from strategy_agent.schemas.data_research import FactorSpec


@dataclass(frozen=True)
class FactorDefinition:
    name: str
    display_name: str
    aliases: tuple[str, ...]
    source_type: str
    dataset: str
    base_datasets: tuple[str, ...] = ()
    base_fields: tuple[str, ...] = ()
    compute_method: str | None = None
    builder: str | None = None
    lookback: str | None = None
    supported_strategy_types: tuple[str, ...] = field(default_factory=tuple)

    def to_spec(self, *, status: str = "ready") -> FactorSpec:
        return FactorSpec(
            name=self.name,
            display_name=self.display_name,
            status=status,
            source_type=self.source_type,  # type: ignore[arg-type]
            dataset=self.dataset,
            base_datasets=list(self.base_datasets),
            base_fields=list(self.base_fields),
            compute_method=self.compute_method,
            lookback=self.lookback,
            rationale=_rationale(self, status),
        )


FACTOR_CATALOG: dict[str, FactorDefinition] = {
    "amount": FactorDefinition(
        name="amount",
        display_name="成交额",
        aliases=("成交额", "成交金额", "traded_amount", "amount"),
        source_type="raw_field",
        dataset="selection_daily",
        base_datasets=("daily_qfq",),
        base_fields=("amount",),
        supported_strategy_types=("cross_sectional_rotation",),
    ),
    "vol": FactorDefinition(
        name="vol",
        display_name="成交量",
        aliases=("成交量", "volume", "vol"),
        source_type="raw_field",
        dataset="selection_daily",
        base_datasets=("daily_qfq",),
        base_fields=("vol",),
        supported_strategy_types=("cross_sectional_rotation",),
    ),
    "total_mv": FactorDefinition(
        name="total_mv",
        display_name="总市值",
        aliases=("市值", "总市值", "总市值最大", "market_cap", "total_mv"),
        source_type="raw_field",
        dataset="selection_daily",
        base_datasets=("daily_basic",),
        base_fields=("total_mv",),
        supported_strategy_types=("cross_sectional_rotation",),
    ),
    "circ_mv": FactorDefinition(
        name="circ_mv",
        display_name="流通市值",
        aliases=("流通市值", "free_float_market_cap", "circ_mv"),
        source_type="raw_field",
        dataset="selection_daily",
        base_datasets=("daily_basic",),
        base_fields=("circ_mv",),
        supported_strategy_types=("cross_sectional_rotation",),
    ),
    "turnover_rate": FactorDefinition(
        name="turnover_rate",
        display_name="换手率",
        aliases=("换手率", "turnover", "turnover_rate"),
        source_type="raw_field",
        dataset="selection_daily",
        base_datasets=("daily_basic",),
        base_fields=("turnover_rate",),
        supported_strategy_types=("cross_sectional_rotation",),
    ),
    "pe_ttm": FactorDefinition(
        name="pe_ttm",
        display_name="滚动市盈率",
        aliases=("pe", "pe_ttm", "市盈率", "滚动市盈率", "低pe"),
        source_type="raw_field",
        dataset="selection_daily",
        base_datasets=("daily_basic",),
        base_fields=("pe_ttm",),
        supported_strategy_types=("cross_sectional_rotation",),
    ),
    "pb": FactorDefinition(
        name="pb",
        display_name="市净率",
        aliases=("pb", "市净率", "低pb"),
        source_type="raw_field",
        dataset="selection_daily",
        base_datasets=("daily_basic",),
        base_fields=("pb",),
        supported_strategy_types=("cross_sectional_rotation",),
    ),
    "monthly_return": FactorDefinition(
        name="monthly_return",
        display_name="上个月涨幅",
        aliases=("涨幅", "收益率", "月涨幅", "上月涨幅", "上个月涨幅", "last_month_return", "previous_month_return", "monthly_return"),
        source_type="derived",
        dataset="selection_factor",
        base_datasets=("daily_qfq",),
        base_fields=("trade_date", "close"),
        compute_method="previous_month_close_return",
        builder="build_monthly_return_factor",
        lookback="previous_month",
        supported_strategy_types=("cross_sectional_rotation",),
    ),
}


for name, label in {
    "return_5d": "近5日收益",
    "return_20d": "近20日收益",
    "return_60d": "近60日收益",
    "volatility_20d": "20日波动率",
    "ma_20": "20日均线",
    "ma_60": "60日均线",
    "ma_distance_20": "价格相对20日均线偏离",
    "volume_ratio_20d": "20日量比",
    "high_20_breakout": "20日新高突破",
    "low_20_breakdown": "20日新低",
    "drawdown_60d": "近60日最大回撤",
    "reversal_20d": "20日反转因子",
}.items():
    FACTOR_CATALOG[name] = FactorDefinition(
        name=name,
        display_name=label,
        aliases=(label, name),
        source_type="derived",
        dataset="selection_factor",
        base_datasets=("daily_qfq",),
        base_fields=("trade_date", "open", "high", "low", "close", "vol"),
        compute_method=name,
        builder=f"build_{name}_factor",
        supported_strategy_types=("cross_sectional_rotation",),
    )


def canonical_factor_name(name: str | None) -> str | None:
    if not name:
        return None
    text = str(name).strip()
    for factor in FACTOR_CATALOG.values():
        if text == factor.name or text in factor.aliases:
            return factor.name
    return text


def factor_definition(name: str | None) -> FactorDefinition | None:
    canonical = canonical_factor_name(name)
    return FACTOR_CATALOG.get(canonical or "")


def supported_ranking_fields() -> set[str]:
    return set(FACTOR_CATALOG)


def _rationale(factor: FactorDefinition, status: str) -> str:
    if factor.source_type == "raw_field":
        return f"{factor.display_name} 是本地数据原始字段。"
    if factor.source_type == "derived":
        return f"{factor.display_name} 可由 {', '.join(factor.base_datasets)} 派生。"
    return f"{factor.display_name} 需要外部数据源。"


__all__ = ["FACTOR_CATALOG", "FactorDefinition", "canonical_factor_name", "factor_definition", "supported_ranking_fields"]
