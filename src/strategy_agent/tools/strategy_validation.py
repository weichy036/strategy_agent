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
    if rule.kind == "indicator_event" and rule.indicator == "ma_cross":
        expected = "bullish_cross" if side == "buy" else "bearish_cross"
        return rule.operator == expected and _valid_ma_pair(rule.params)
    if rule.kind == "comparison_rule" and rule.indicator == "ma":
        expected = "cross_above" if side == "buy" else "cross_below"
        return rule.operator == expected and _valid_ma_comparison(rule)
    if rule.kind == "comparison_rule":
        return rule.operator in {"gt", "lt", "eq"} and bool(rule.indicator)
    return False


def _valid_ma_pair(params: dict) -> bool:
    try:
        fast = int(params.get("fast", 0))
        slow = int(params.get("slow", 0))
    except (TypeError, ValueError):
        return False
    return fast > 0 and slow > 0 and fast != slow


def _valid_ma_comparison(rule) -> bool:
    value = rule.value if isinstance(rule.value, dict) else {}
    try:
        left = int((rule.params or {}).get("period", 0))
        right = int((value.get("params") or {}).get("period", 0))
    except (TypeError, ValueError):
        return False
    return value.get("indicator") == "ma" and left > 0 and right > 0 and left != right


_SUPPORTED_RANKING_FIELDS = supported_ranking_fields()
