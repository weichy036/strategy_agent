from __future__ import annotations

from strategy_agent.schemas.state import SessionWorkflowState


def create_initial_state(query: str = "") -> SessionWorkflowState:
    return SessionWorkflowState(current_query=query)
