from __future__ import annotations

from strategy_agent.services.execution_gate import should_execute_backtest


def test_gate_allows_backtestable_request() -> None:
    assert should_execute_backtest(
        {"is_backtest_request": True, "is_backtestable_now": True},
        {"needs_clarification": False},
    )


def test_gate_allows_later_strategy_stage_to_override_intent_uncertainty() -> None:
    assert should_execute_backtest(
        {"is_backtest_request": True, "is_backtestable_now": False},
        {"needs_clarification": False},
    )


def test_gate_blocks_missing_required_fields() -> None:
    assert not should_execute_backtest(
        {"is_backtest_request": True, "is_backtestable_now": False},
        {"needs_clarification": True},
    )


def test_gate_blocks_non_backtest_answer() -> None:
    assert not should_execute_backtest(
        {"is_backtest_request": False, "is_backtestable_now": False},
        {"needs_clarification": False},
    )


def test_gate_blocks_missing_data() -> None:
    assert not should_execute_backtest(
        {"is_backtest_request": True, "is_backtestable_now": True},
        {"needs_clarification": False},
        {"is_ready": False},
    )


if __name__ == "__main__":
    test_gate_allows_backtestable_request()
    test_gate_allows_later_strategy_stage_to_override_intent_uncertainty()
    test_gate_blocks_missing_required_fields()
    test_gate_blocks_non_backtest_answer()
    test_gate_blocks_missing_data()
    print("ok")
