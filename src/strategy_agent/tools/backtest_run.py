from __future__ import annotations

from strategy_agent.domain.backtest import run_backtest_for_strategy
from strategy_agent.schemas.strategy_schema import StrategySchema
from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse


def run_backtest(strategy_schema: dict, execution_options: dict | None = None) -> ToolResponse[dict]:
    try:
        schema = StrategySchema.model_validate(strategy_schema)
        result = run_backtest_for_strategy(schema)
        return ToolResponse(
            ok=True,
            data=result,
            meta={
                "execution_options": execution_options or {},
                "assumptions_version": "v1",
            },
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResponse(
            ok=False,
            error=ToolError(
                code="backtest_execution_failed",
                message="回测执行失败",
                details={
                    "reason": str(exc),
                    "strategy_type": strategy_schema.get("strategy_type"),
                },
            ),
            meta={"execution_options": execution_options or {}},
        )
