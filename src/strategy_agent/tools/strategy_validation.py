from __future__ import annotations

from strategy_agent.schemas.strategy_schema import StrategySchema
from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse
from strategy_agent.services.factor_catalog import supported_ranking_fields


def validate_strategy_schema(strategy_schema: dict) -> ToolResponse[dict]:
    try:
        schema = StrategySchema.model_validate(strategy_schema)
    except Exception as exc:  # noqa: BLE001
        return ToolResponse(
            ok=False,
            error=ToolError(
                code="strategy_schema_invalid",
                message="策略对象不符合 Schema",
                details={"reason": str(exc)},
            ),
        )

    missing_fields: list[str] = []
    invalid_fields: list[str] = []
    warnings: list[str] = []

    if schema.universe.type == "instrument" and not schema.universe.symbols:
        missing_fields.append("universe.symbols")

    if schema.strategy_type in {"signal_trading", "rule_based_timing"}:
        if not schema.signals or not schema.signals.buy:
            missing_fields.append("signals.buy")
        if not schema.signals or not schema.signals.sell:
            missing_fields.append("signals.sell")
        if schema.signals:
            invalid_fields.extend(_invalid_signal_fields(schema.signals.buy, "buy"))
            invalid_fields.extend(_invalid_signal_fields(schema.signals.sell, "sell"))
    if schema.strategy_type == "cross_sectional_rotation":
        if not schema.selection or not schema.selection.ranking:
            missing_fields.append("selection.ranking")
        elif schema.selection.ranking.sort_by not in _SUPPORTED_RANKING_FIELDS:
            invalid_fields.append("selection.ranking.sort_by")
        if not schema.portfolio or schema.portfolio.position_count is None:
            missing_fields.append("portfolio.position_count")
        if not schema.portfolio or not schema.portfolio.weight_method:
            missing_fields.append("portfolio.weight_method")
    if schema.strategy_type == "screen_and_hold":
        if not schema.selection or not schema.selection.filters:
            missing_fields.append("selection.filters")
        if not schema.selection or not schema.selection.hold_period:
            missing_fields.append("selection.hold_period")

    if schema.period.start is None or schema.period.end is None:
        warnings.append("period.start_or_end_default_needed")

    return ToolResponse(
        ok=True,
        data={
            "is_valid": not invalid_fields,
            "is_complete": not missing_fields and not invalid_fields,
            "missing_fields": missing_fields,
            "invalid_fields": invalid_fields,
            "warnings": warnings,
        },
        meta={"schema_version": schema.schema_version},
    )


def _invalid_signal_fields(rules: list, side: str) -> list[str]:
    invalid: list[str] = []
    for index, rule in enumerate(rules):
        if _is_supported_signal_rule(rule, side):
            continue
        invalid.append(f"signals.{side}[{index}]")
    return invalid


def _is_supported_signal_rule(rule, side: str) -> bool:
    if rule.kind == "indicator_event" and rule.indicator == "macd":
        expected = "bullish_cross" if side == "buy" else "bearish_cross"
        return rule.operator == expected
    if rule.kind == "comparison_rule":
        return rule.operator in {"gt", "lt", "eq"} and bool(rule.indicator)
    return False


_SUPPORTED_RANKING_FIELDS = supported_ranking_fields()
