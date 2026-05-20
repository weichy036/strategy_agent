from __future__ import annotations

from strategy_agent.schemas.result_page import ResultPage
from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse


def assemble_result_page(
    strategy_schema: dict,
    backtest_result: dict,
    metrics: dict,
    explanations: dict,
) -> ToolResponse[dict]:
    equity_curve = backtest_result.get("equity_curve") or {}
    if not equity_curve:
        return ToolResponse(
            ok=False,
            error=ToolError(
                code="report_assembly_failed",
                message="结果页组装失败，缺少必需的收益曲线数据",
            ),
        )

    result_page = ResultPage(
        summary={
            "strategy_name": strategy_schema.get("name"),
            "summary_text": explanations.get("summary_text"),
            "risk_text": explanations.get("risk_text"),
        },
        metric_cards=metrics,
        equity_curve={"series": equity_curve},
        drawdown_curve={"series": backtest_result.get("drawdown_curve") or []},
        trade_stats={
            "trade_log_size": len(backtest_result.get("trade_log") or []),
            "position_log_size": len(backtest_result.get("position_log") or []),
        },
        risk_disclosures=[
            explanations.get("limitations_text") or "回测结果不代表未来表现。",
        ],
    )
    return ToolResponse(
        ok=True,
        data={"result_page": result_page.model_dump()},
        meta={"result_schema_version": "v1"},
    )
