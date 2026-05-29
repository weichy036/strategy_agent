from __future__ import annotations

from strategy_agent.domain.market_data import (
    get_bar_frame,
    get_benchmark_frame,
    get_daily_basic_by_instrument,
    get_daily_basic_frame,
    get_latest_trade_date,
    get_selection_daily_frame,
)
from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse


def query_market_data(
    query_type: str,
    instrument: str | None = None,
    price_mode: str = "qfq",
    start_date: str | None = None,
    end_date: str = "latest",
    trade_date: str = "latest",
) -> ToolResponse[dict]:
    if query_type == "latest_trade_date":
        latest = get_latest_trade_date()
        return ToolResponse(ok=True, data={"query_type": query_type, "latest_trade_date": latest})

    if query_type == "bar_frame" and instrument:
        frame = get_bar_frame(instrument, price_mode=price_mode, start_date=start_date, end_date=end_date)
    elif query_type == "benchmark_frame":
        frame = get_benchmark_frame(instrument or "000300.SH", start_date=start_date, end_date=end_date)
    elif query_type == "daily_basic_frame":
        frame = get_daily_basic_frame(trade_date)
    elif query_type == "selection_daily_frame":
        frame = get_selection_daily_frame(trade_date)
    elif query_type == "daily_basic_by_instrument" and instrument:
        frame = get_daily_basic_by_instrument(instrument, trade_date=trade_date)
    else:
        return ToolResponse(
            ok=False,
            error=ToolError(
                code="market_data_query_invalid",
                message="不支持的数据查询类型或缺少必要参数",
                details={"query_type": query_type, "instrument": instrument},
            ),
        )

    if frame.empty:
        return ToolResponse(
            ok=False,
            error=ToolError(
                code="market_data_not_found",
                message="未找到匹配的市场数据",
                details={"query_type": query_type, "instrument": instrument},
            ),
        )

    return ToolResponse(
        ok=True,
        data={
            "query_type": query_type,
            "row_count": len(frame),
            "columns": list(frame.columns),
            "records": frame.head(200).to_dict(orient="records"),
        },
    )
