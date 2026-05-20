from __future__ import annotations

from uuid import uuid4

from strategy_agent.schemas.tool_contracts import ToolResponse
from strategy_agent.tools.backtest_run import run_backtest
from strategy_agent.tools.clarification_decision import decide_clarification
from strategy_agent.tools.metrics_compute import compute_metrics
from strategy_agent.tools.artifact_store import store_artifact
from strategy_agent.tools.report_assembly import assemble_result_page
from strategy_agent.tools.strategy_parse import parse_strategy_query_tool
from strategy_agent.tools.strategy_validation import validate_strategy_schema


def run_research_query(query: str, session_id: str = "local") -> ToolResponse[dict]:
    run_id = uuid4().hex[:8]
    parsed = parse_strategy_query_tool(query)
    if not parsed.ok:
        return parsed

    assert parsed.data is not None
    strategy_draft = parsed.data["strategy_draft"]
    strategy_id = strategy_draft.get("strategy_id")

    draft_artifact = store_artifact(
        artifact_type="strategy_schema",
        session_id=session_id,
        content=strategy_draft,
        strategy_id=strategy_id,
        run_id=run_id,
    )
    validation = validate_strategy_schema(strategy_draft)
    if not validation.ok:
        return validation

    assert validation.data is not None
    clarification = decide_clarification(strategy_draft, validation.data, {"user_query": query})
    if not clarification.ok:
        return clarification

    assert clarification.data is not None
    if not clarification.data["ready_to_execute"]:
        return ToolResponse(
            ok=True,
            data={
                "status": "needs_clarification",
                "query": query,
                "parsed": parsed.data,
                "validation": validation.data,
                "clarification": clarification.data,
                "artifacts": {
                    "strategy_schema": draft_artifact.data if draft_artifact.ok else None,
                },
            },
            meta={"workflow": "research_flow_v1"},
        )

    backtest = run_backtest(strategy_draft)
    if not backtest.ok:
        return ToolResponse(
            ok=False,
            data={
                "status": "backtest_failed",
                "query": query,
                "parsed": parsed.data,
                "validation": validation.data,
                "clarification": clarification.data,
            },
            error=backtest.error,
            meta={"workflow": "research_flow_v1"},
        )

    assert backtest.data is not None
    metrics = compute_metrics(backtest.data)
    if not metrics.ok:
        return metrics

    assert metrics.data is not None
    explanations = {
        "summary_text": "该结果基于本地历史日线数据和当前策略规则生成，核心收益曲线已包含在结果页中。",
        "risk_text": "策略结果可能受到参数、交易成本、滑点和样本区间影响，回测结果不代表未来表现。",
        "limitations_text": "当前 MVP 默认使用下一交易日开盘价成交，并使用固定佣金和滑点假设。",
    }
    report = assemble_result_page(strategy_draft, backtest.data, metrics.data, explanations)
    if not report.ok:
        return report

    assert report.data is not None
    backtest_artifact = store_artifact(
        artifact_type="backtest_result",
        session_id=session_id,
        content=backtest.data,
        strategy_id=strategy_id,
        run_id=run_id,
    )
    equity_artifact = store_artifact(
        artifact_type="equity_curve",
        session_id=session_id,
        content=backtest.data.get("equity_curve") or [],
        strategy_id=strategy_id,
        run_id=run_id,
    )
    report_artifact = store_artifact(
        artifact_type="report",
        session_id=session_id,
        content=report.data["result_page"],
        strategy_id=strategy_id,
        run_id=run_id,
    )

    return ToolResponse(
        ok=True,
        data={
            "status": "completed",
            "query": query,
            "parsed": parsed.data,
            "validation": validation.data,
            "clarification": clarification.data,
            "backtest": backtest.data,
            "metrics": metrics.data,
            "result_page": report.data["result_page"],
            "artifacts": {
                "strategy_schema": draft_artifact.data if draft_artifact.ok else None,
                "backtest_result": backtest_artifact.data if backtest_artifact.ok else None,
                "equity_curve": equity_artifact.data if equity_artifact.ok else None,
                "report": report_artifact.data if report_artifact.ok else None,
            },
        },
        meta={"workflow": "research_flow_v1", "session_id": session_id, "run_id": run_id},
    )
