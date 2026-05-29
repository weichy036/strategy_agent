from __future__ import annotations

from typing import Any


def should_execute_backtest(
    intent: dict[str, Any] | None,
    clarification: dict[str, Any] | None,
    data_availability: dict[str, Any] | None = None,
) -> bool:
    if intent and intent.get("is_backtest_request") is False:
        return False
    if clarification and clarification.get("needs_clarification"):
        return False
    if data_availability and data_availability.get("can_continue_backtest") is False:
        return False
    if data_availability and data_availability.get("is_ready") is False:
        return False
    return True


__all__ = ["should_execute_backtest"]
