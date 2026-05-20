from __future__ import annotations

from strategy_agent.schemas.tool_contracts import ToolResponse
from strategy_agent.services.research_flow import run_research_query


def run_research_query_tool(query: str, session_id: str = "local") -> ToolResponse[dict]:
    return run_research_query(query=query, session_id=session_id)
