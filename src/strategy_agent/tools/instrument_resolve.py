from __future__ import annotations

from strategy_agent.domain.instruments import resolve_instrument
from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse


def resolve_instrument_tool(query: str, allowed_asset_types: list[str] | None = None, market: str = "CN") -> ToolResponse[dict]:
    resolved = resolve_instrument(query)
    instrument = resolved.get("instrument")
    if instrument and allowed_asset_types and instrument["asset_type"] not in allowed_asset_types:
        return ToolResponse(
            ok=False,
            data=resolved,
            error=ToolError(
                code="instrument_not_allowed",
                message="标的类型不在允许范围内",
                details={"query": query, "allowed_asset_types": allowed_asset_types},
            ),
        )
    if resolved["resolved"]:
        return ToolResponse(ok=True, data=resolved, meta={"query": query, "market": market})
    error_code = "instrument_ambiguous" if resolved["is_ambiguous"] else "instrument_not_found"
    return ToolResponse(
        ok=False,
        data=resolved,
        error=ToolError(code=error_code, message="无法唯一识别标的", details={"query": query}),
        meta={"query": query, "market": market},
    )
