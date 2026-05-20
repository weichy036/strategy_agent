from __future__ import annotations

from strategy_agent.schemas.tool_contracts import ToolResponse


DEFAULTABLE_FIELDS = {
    "period.start",
    "period.end",
    "execution.buy_price",
    "execution.sell_price",
    "costs.commission_bps",
    "costs.slippage_bps",
    "constraints.tradability_filters",
    "portfolio.weight_method",
}


def decide_clarification(strategy_draft: dict, validation_result: dict, context: dict | None = None) -> ToolResponse[dict]:
    missing_fields = list(validation_result.get("missing_fields", []))
    must_ask_fields = [field for field in missing_fields if field not in DEFAULTABLE_FIELDS]
    defaultable_fields = [field for field in missing_fields if field in DEFAULTABLE_FIELDS]
    next_question = None
    if must_ask_fields:
        field = must_ask_fields[0]
        if field == "universe.symbols":
            next_question = "我还缺一个关键条件：你想回测哪个标的？例如沪深300ETF、创业板ETF，或具体股票代码。"
        elif field == "signals.sell":
            next_question = "我还缺一个关键条件：你的卖出规则是什么？"
        elif field == "portfolio.position_count":
            next_question = "我还缺一个关键条件：你希望持有多少只股票？"
        elif field == "selection.hold_period":
            next_question = "我还缺一个关键条件：筛选出来的股票打算持有多久？"
        else:
            next_question = f"我还缺一个关键条件：请补充 {field}。"
    return ToolResponse(
        ok=True,
        data={
            "must_ask_fields": must_ask_fields,
            "defaultable_fields": defaultable_fields,
            "ready_to_execute": not must_ask_fields,
            "next_question": next_question,
            "strategy_draft": strategy_draft,
            "context": context or {},
        },
    )
