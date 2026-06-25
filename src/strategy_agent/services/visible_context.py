from __future__ import annotations

from copy import deepcopy
from typing import Any

from strategy_agent.services.runtime_models import AgentTurnResult


def build_visible_context(*, query: str, result: AgentTurnResult) -> dict[str, Any]:
    """Build the compact state block that future prompts should inherit."""

    data = result.data if isinstance(result.data, dict) else {}
    strategy_schema = _as_dict(data.get("strategy_schema"))
    result_page = _as_dict(data.get("result_page"))
    backtest = _as_dict(data.get("backtest"))
    metrics = _as_dict(data.get("metrics"))
    conversation_context = _as_dict(data.get("conversation_context"))
    explanation = _as_dict(data.get("explanations"))

    return {
        "last_user_query": query,
        "last_status": result.status,
        "last_goal": _goal_text(conversation_context, query),
        "current_strategy_summary": _strategy_summary(strategy_schema),
        "current_strategy_schema": _compact_strategy_schema(strategy_schema),
        "latest_result_summary": _result_summary(result_page, metrics, backtest, explanation),
        "latest_artifacts": _artifact_refs(result_page),
        "follow_up_hints": _follow_up_hints(conversation_context, strategy_schema),
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _goal_text(conversation_context: dict[str, Any], query: str) -> str:
    rewritten = conversation_context.get("rewritten_query")
    return str(rewritten or query)


def _strategy_summary(schema: dict[str, Any]) -> str | None:
    if not schema:
        return None
    strategy_type = schema.get("strategy_type") or "unknown_strategy"
    universe = schema.get("universe") or {}
    selection = schema.get("selection") or {}
    ranking = selection.get("ranking") if isinstance(selection, dict) else {}
    portfolio = schema.get("portfolio") or {}
    signals = schema.get("signals") or {}

    if strategy_type == "cross_sectional_rotation":
        scope = universe.get("scope") or universe.get("type") or "未指定股票池"
        top_n = ranking.get("top_n") if isinstance(ranking, dict) else portfolio.get("position_count")
        sort_by = ranking.get("sort_by") if isinstance(ranking, dict) else None
        lookback = ranking.get("lookback") if isinstance(ranking, dict) else None
        hold = selection.get("hold_period") if isinstance(selection, dict) else {}
        frequency = hold.get("frequency") if isinstance(hold, dict) else portfolio.get("rebalance_frequency")
        return f"{scope}，按 {sort_by or '排序因子'}（{lookback or '默认窗口'}）选择前 {top_n or 'N'} 只，{frequency or '定期'}调仓，等权持有。"

    symbols = universe.get("symbols") or []
    symbol_text = "、".join(symbols) if symbols else universe.get("scope") or universe.get("type") or "未指定标的"
    buy = signals.get("buy") if isinstance(signals, dict) else None
    sell = signals.get("sell") if isinstance(signals, dict) else None
    return f"{symbol_text} 的 {strategy_type} 策略，买入规则={buy or '未指定'}，卖出规则={sell or '未指定'}。"


def _compact_strategy_schema(schema: dict[str, Any]) -> dict[str, Any] | None:
    if not schema:
        return None
    keep_keys = {
        "schema_version",
        "strategy_id",
        "name",
        "market",
        "strategy_type",
        "universe",
        "period",
        "signals",
        "selection",
        "portfolio",
        "execution",
        "costs",
        "constraints",
        "metadata",
    }
    return {key: deepcopy(value) for key, value in schema.items() if key in keep_keys}


def _result_summary(
    result_page: dict[str, Any],
    metrics: dict[str, Any],
    backtest: dict[str, Any],
    explanation: dict[str, Any],
) -> dict[str, Any] | None:
    summary = _as_dict(result_page.get("summary"))
    if not summary and not metrics and not backtest and not explanation:
        return None

    metric_cards = _as_dict(result_page.get("metric_cards"))
    return_metrics = _as_dict(metric_cards.get("return_metrics")) or _as_dict(metrics.get("return_metrics"))
    risk_metrics = _as_dict(metric_cards.get("risk_metrics")) or _as_dict(metrics.get("risk_metrics"))
    trading_metrics = _as_dict(metric_cards.get("trading_metrics")) or _as_dict(metrics.get("trading_metrics"))

    return {
        "strategy_name": summary.get("strategy_name"),
        "summary_text": summary.get("summary_text") or explanation.get("summary_text"),
        "risk_text": summary.get("risk_text") or explanation.get("risk_text"),
        "date_range": backtest.get("date_range"),
        "return_metrics": return_metrics,
        "risk_metrics": risk_metrics,
        "trading_metrics": trading_metrics,
    }


def _artifact_refs(result_page: dict[str, Any]) -> dict[str, Any]:
    refs: dict[str, Any] = {}
    equity = _as_dict(result_page.get("equity_curve"))
    if equity.get("artifact"):
        refs["equity_curve"] = equity["artifact"]
    trade_stats = _as_dict(result_page.get("trade_stats"))
    for key in ("selection_artifact", "trade_artifact"):
        if trade_stats.get(key):
            refs[key] = trade_stats[key]
    return refs


def _follow_up_hints(conversation_context: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    mutable_fields = []
    if schema.get("strategy_type") == "cross_sectional_rotation":
        mutable_fields.extend(["selection.ranking.top_n", "portfolio.position_count"])
    if schema.get("strategy_type") == "signal_trading":
        mutable_fields.extend(["signals.buy", "signals.sell", "universe.symbols"])
    return {
        "can_inherit_strategy": bool(schema),
        "last_turn_type": conversation_context.get("turn_type"),
        "patch_hints": conversation_context.get("patch_hints") or {},
        "mutable_fields": mutable_fields,
    }


__all__ = ["build_visible_context"]
