from strategy_agent.services.observability import build_observability


def test_build_observability_pairs_tool_span_and_usage():
    timeline = [
        {
            "event_type": "tool_start",
            "actor": "run_backtest",
            "status": "running",
            "message": "start",
            "timestamp": "2026-05-29T10:00:00+00:00",
        },
        {
            "event_type": "tool_done",
            "actor": "run_backtest",
            "status": "success",
            "message": "done",
            "timestamp": "2026-05-29T10:00:02+00:00",
        },
    ]
    usage = {
        "total": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "items": [{"actor": "StrategyDesignerAgent", "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}],
    }

    data = build_observability(
        timeline=timeline,
        usage=usage,
        result_data={"backtest": {"run_id": "bt_demo"}},
        status="completed",
    )

    assert data["run_id"] == "bt_demo"
    assert data["status"] == "completed"
    assert data["latency_ms"] >= 2000
    assert data["spans"][0]["name"] == "run_backtest"
    assert data["spans"][0]["type"] == "tool"
    assert any(span["type"] == "llm" for span in data["spans"])
