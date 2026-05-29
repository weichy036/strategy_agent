from __future__ import annotations

from strategy_agent.schemas.result_page import ResultPage
from strategy_agent.services.artifact_manager import artifact_url, build_artifact_name, persist_artifact_content
from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse


def assemble_result_page(
    strategy_schema: dict,
    backtest_result: dict,
    metrics: dict,
    explanations: dict,
    session_id: str | None = None,
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

    strategy_name = display_strategy_name(strategy_schema)
    equity_artifact = _persist_equity_curve_svg(session_id, strategy_schema, backtest_result, equity_curve, strategy_name=strategy_name)
    selection_artifact = _persist_selection_log_json(session_id, strategy_schema, backtest_result, strategy_name=strategy_name)
    trade_artifact = _persist_log_json("trade_log", session_id, strategy_schema, backtest_result, strategy_name=strategy_name)
    result_page = ResultPage(
        summary={
            "strategy_name": strategy_name,
            "summary_text": explanations.get("summary_text") or f"{strategy_name} 回测完成。",
            "risk_text": explanations.get("risk_text"),
        },
        metric_cards=metrics,
        equity_curve={"series": equity_curve, "artifact": equity_artifact},
        drawdown_curve={"series": backtest_result.get("drawdown_curve") or []},
        trade_stats={
            "trade_log_size": len(backtest_result.get("trade_log") or []),
            "position_log_size": len(backtest_result.get("position_log") or []),
            "selection_snapshots": _selection_snapshots(backtest_result.get("selection_log") or []),
            "selection_artifact": selection_artifact,
            "trade_snapshots": _trade_snapshots(backtest_result.get("trade_log") or []),
            "trade_artifact": trade_artifact,
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


def _persist_equity_curve_svg(
    session_id: str | None,
    strategy_schema: dict,
    backtest_result: dict,
    equity_curve: list[dict],
    *,
    strategy_name: str,
) -> dict | None:
    if not session_id:
        return None
    run_id = str(backtest_result.get("run_id") or "")
    strategy_id = str(strategy_schema.get("strategy_id") or strategy_schema.get("name") or strategy_name or "strategy")
    name = build_artifact_name("equity_curve", session_id, strategy_id=_safe_part(strategy_id), run_id=_safe_part(run_id), ext="svg")
    try:
        file_path = persist_artifact_content(
            session_id=session_id,
            name=name,
            content=_equity_curve_svg(equity_curve),
            content_type="image/svg+xml",
        )
    except Exception:  # noqa: BLE001 - artifact persistence is an optimization; keep result rendering available.
        return None
    return {
        "artifact_id": name,
        "artifact_type": "equity_curve",
        "uri": f"artifact://{session_id}/{name}",
        "url": artifact_url(session_id, name),
        "file_path": str(file_path),
        "content_type": "image/svg+xml",
}


def _persist_log_json(
    log_name: str,
    session_id: str | None,
    strategy_schema: dict,
    backtest_result: dict,
    *,
    strategy_name: str,
) -> dict | None:
    log = backtest_result.get(log_name) or []
    if not session_id or not log:
        return None
    run_id = str(backtest_result.get("run_id") or "")
    strategy_id = str(strategy_schema.get("strategy_id") or strategy_schema.get("name") or strategy_name or "strategy")
    name = build_artifact_name(log_name, session_id, strategy_id=_safe_part(strategy_id), run_id=_safe_part(run_id), ext="json")
    payload = {
        "strategy_name": strategy_name,
        "run_id": run_id,
        "date_range": backtest_result.get("date_range") or {},
        log_name: log,
    }
    try:
        file_path = persist_artifact_content(
            session_id=session_id,
            name=name,
            content=payload,
            content_type="application/json",
        )
    except Exception:  # noqa: BLE001 - artifact persistence is optional for rendering.
        return None
    return {
        "artifact_id": name,
        "artifact_type": log_name,
        "uri": f"artifact://{session_id}/{name}",
        "url": artifact_url(session_id, name),
        "file_path": str(file_path),
        "content_type": "application/json",
    }


def _persist_selection_log_json(
    session_id: str | None,
    strategy_schema: dict,
    backtest_result: dict,
    *,
    strategy_name: str,
) -> dict | None:
    selection_log = backtest_result.get("selection_log") or []
    if not session_id or not selection_log:
        return None
    run_id = str(backtest_result.get("run_id") or "")
    strategy_id = str(strategy_schema.get("strategy_id") or strategy_schema.get("name") or strategy_name or "strategy")
    name = build_artifact_name("selection_log", session_id, strategy_id=_safe_part(strategy_id), run_id=_safe_part(run_id), ext="json")
    payload = {
        "strategy_name": strategy_name,
        "run_id": run_id,
        "date_range": backtest_result.get("date_range") or {},
        "selection_log": selection_log,
    }
    try:
        file_path = persist_artifact_content(
            session_id=session_id,
            name=name,
            content=payload,
            content_type="application/json",
        )
    except Exception:  # noqa: BLE001 - artifact persistence is optional for rendering.
        return None
    return {
        "artifact_id": name,
        "artifact_type": "selection_log",
        "uri": f"artifact://{session_id}/{name}",
        "url": artifact_url(session_id, name),
        "file_path": str(file_path),
        "content_type": "application/json",
    }


def _equity_curve_svg(series: list[dict], width: int = 760, height: int = 250, pad: int = 18) -> str:
    values = [float(point["nav"]) for point in series if "nav" in point]
    if len(values) < 2:
        values = [1.0, 1.0]
    min_value = min(values)
    max_value = max(values)
    span = max(max_value - min_value, 1e-9)
    points = []
    for idx, value in enumerate(values):
        x = pad + idx * ((width - pad * 2) / (len(values) - 1))
        y = height - pad - (value - min_value) * ((height - pad * 2) / span)
        points.append(f"{x:.2f},{y:.2f}")
    point_text = " ".join(points)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <path d="M {pad},{height - pad} L {point_text} L {width - pad},{height - pad} Z" fill="rgba(17,17,17,0.07)"/>
  <polyline points="{point_text}" fill="none" stroke="#111111" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" stroke="#e8e3da" stroke-width="1"/>
</svg>"""


def _safe_part(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)[:80]


def _selection_snapshots(selection_log: list[dict], limit: int = 6) -> list[dict]:
    snapshots = []
    for item in selection_log[-limit:]:
        symbols = [str(symbol) for symbol in item.get("symbols") or []]
        snapshots.append(
            {
                "trade_date": item.get("trade_date"),
                "target_count": item.get("target_count"),
                "executed_count": item.get("executed_count"),
                "symbols": symbols[:20],
            }
        )
    return snapshots


def _trade_snapshots(trade_log: list[dict], limit: int = 20) -> list[dict]:
    enriched = _enrich_trade_returns(trade_log)
    return enriched[-limit:]


def _enrich_trade_returns(trade_log: list[dict]) -> list[dict]:
    positions: dict[str, list[dict[str, float]]] = {}
    cumulative = 0.0
    snapshots = []
    for item in trade_log:
        symbol = str(item.get("symbol") or "")
        side = str(item.get("side") or "")
        shares = float(item.get("shares") or 0)
        price = float(item.get("price") or 0)
        amount = shares * price
        realized = None
        if side == "buy" and symbol and shares > 0:
            positions.setdefault(symbol, []).append({"shares": shares, "price": price})
        elif side == "sell" and symbol and shares > 0:
            realized = _realized_profit(positions.setdefault(symbol, []), shares, price)
            cumulative += realized
        snapshots.append(
            {
                "trade_date": item.get("trade_date"),
                "symbol": symbol,
                "side": side,
                "shares": shares,
                "price": price,
                "amount": amount,
                "realized_profit": realized,
                "cumulative_profit": cumulative if side == "sell" else None,
            }
        )
    return snapshots


def _realized_profit(lots: list[dict[str, float]], sell_shares: float, sell_price: float) -> float:
    remaining = sell_shares
    cost = 0.0
    while remaining > 1e-12 and lots:
        lot = lots[0]
        matched = min(remaining, lot["shares"])
        cost += matched * lot["price"]
        lot["shares"] -= matched
        remaining -= matched
        if lot["shares"] <= 1e-12:
            lots.pop(0)
    return sell_shares * sell_price - cost


def display_strategy_name(strategy_schema: dict) -> str:
    if strategy_schema.get("name"):
        return str(strategy_schema["name"])
    strategy_type = strategy_schema.get("strategy_type")
    if strategy_type in {"signal_trading", "rule_based_timing"}:
        return _signal_strategy_name(strategy_schema)
    if strategy_type == "cross_sectional_rotation":
        return _rotation_strategy_name(strategy_schema)
    return "策略"


def _signal_strategy_name(strategy_schema: dict) -> str:
    symbols = ((strategy_schema.get("universe") or {}).get("symbols") or [])
    symbol = str(symbols[0]) if symbols else "单标的"
    signals = strategy_schema.get("signals") or {}
    rules = (signals.get("buy") or []) + (signals.get("sell") or [])
    if any((rule or {}).get("indicator") == "macd" for rule in rules):
        return f"{symbol} MACD 策略"
    if any((rule or {}).get("indicator") == "rsi" for rule in rules):
        return f"{symbol} RSI 策略"
    return f"{symbol} 择时策略"


def _rotation_strategy_name(strategy_schema: dict) -> str:
    selection = strategy_schema.get("selection") or {}
    ranking = selection.get("ranking") or {}
    sort_by = ranking.get("sort_by") or "因子"
    top_n = ranking.get("top_n") or (strategy_schema.get("portfolio") or {}).get("position_count") or ""
    factor_name = {
        "monthly_return": "上月涨幅",
        "amount": "成交额",
        "total_mv": "总市值",
        "circ_mv": "流通市值",
        "turnover_rate": "换手率",
        "pe_ttm": "PE",
        "pb": "PB",
    }.get(str(sort_by), str(sort_by))
    top_text = f"TOP{top_n}" if top_n else "TOP"
    return f"{factor_name} {top_text} 月度轮动策略"
