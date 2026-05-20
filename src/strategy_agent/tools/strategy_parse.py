from __future__ import annotations

from strategy_agent.domain.strategy_parser import parse_strategy_query
from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse


def parse_strategy_query_tool(query: str) -> ToolResponse[dict]:
    parsed = parse_strategy_query(query)
    if parsed["recognized"]:
        return ToolResponse(ok=True, data=parsed, meta={"parser": parsed["parser"]})
    return ToolResponse(
        ok=False,
        data=parsed,
        error=ToolError(
            code="strategy_query_not_recognized",
            message="当前规则解析器暂时无法识别该策略问题",
            details={"query": query},
        ),
        meta={"parser": parsed["parser"]},
    )
