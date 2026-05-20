from __future__ import annotations

from strategy_agent.schemas.strategy_schema import StrategySchema
from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse


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
    if schema.strategy_type == "cross_sectional_rotation":
        if not schema.selection or not schema.selection.ranking:
            missing_fields.append("selection.ranking")
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
            "is_complete": not missing_fields,
            "missing_fields": missing_fields,
            "invalid_fields": invalid_fields,
            "warnings": warnings,
        },
        meta={"schema_version": schema.schema_version},
    )
