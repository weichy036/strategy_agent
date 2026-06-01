import asyncio

from google.adk.artifacts import FileArtifactService
from google.adk.workflow import Workflow

from strategy_agent.app import build_runner
from strategy_agent.agents.orchestrator import create_research_orchestrator_agent
from strategy_agent.services.adk_skills import create_quant_backtest_skill_toolset
from strategy_agent.services.observability import build_observability
from strategy_agent.services.response_slimmer import slim_response_data, slim_tool_calls
from strategy_agent.services.result_collector import StrategyRunResultCollector
from strategy_agent.services.runtime_models import AdkStreamEvent
from strategy_agent.services.state_keys import AgentStateKeys


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


def test_result_collector_reads_adk_state_delta_outputs():
    collector = StrategyRunResultCollector()

    collector.record(
        AdkStreamEvent(
            type="state_delta",
            author="StrategyExecutionAgent",
            payload={
                AgentStateKeys.RESULT_PAGE: {
                    "equity_curve": {
                        "series": [{"date": "2024-01-01", "value": 1.0}],
                    }
                },
                "workflow.status": "completed",
            },
        )
    )

    result = collector.build()

    assert result.status == "completed"
    assert result.data["result_page"]["equity_curve"]["series"]


def test_result_collector_parses_json_string_state_delta_outputs():
    collector = StrategyRunResultCollector()

    collector.record(
        AdkStreamEvent(
            type="state_delta",
            author="IntentClassifierAgent",
            payload={
                AgentStateKeys.INTENT_CLASSIFICATION: (
                    '{"intent_type":"general_chat","confidence":0.9,'
                    '"is_backtest_request":false,"is_backtestable_now":false,'
                    '"missing_fields":[],"reason":"普通问答"}'
                )
            },
        )
    )

    assert collector.build().data["intent"]["is_backtest_request"] is False


def test_quant_backtest_skill_toolset_loads_local_skill():
    toolset = create_quant_backtest_skill_toolset()
    tools = asyncio.run(toolset.get_tools())

    assert {tool.name for tool in tools} >= {"list_skills", "load_skill", "load_skill_resource", "run_skill_script"}
    assert toolset._list_skills()[0].name == "quant-backtest-cn"  # noqa: SLF001


def test_runner_uses_adk_file_artifact_service():
    runner = build_runner()

    assert isinstance(runner.artifact_service, FileArtifactService)


def test_orchestrator_uses_adk_workflow_chain():
    orchestrator = create_research_orchestrator_agent()

    assert isinstance(orchestrator, Workflow)
    assert [(edge.from_node.name, edge.to_node.name) for edge in orchestrator.graph.edges] == [
        ("__START__", "IntentClassifierAgent"),
        ("IntentClassifierAgent", "ClarificationAgent"),
        ("ClarificationAgent", "StrategyDesignerAgent"),
        ("StrategyDesignerAgent", "DataResearchAgent"),
        ("DataResearchAgent", "StrategyExecutionAgent"),
        ("StrategyExecutionAgent", "ResultExplanationAgent"),
    ]


def test_response_slimmer_keeps_artifacts_without_large_series():
    data = {
        "backtest": {
            "run_id": "bt_demo",
            "strategy_id": "demo",
            "date_range": {"start": "20240101", "end": "20240103"},
            "summary": {"total_return": 0.1},
            "equity_curve": [
                {"trade_date": "20240101", "nav": 1.0},
                {"trade_date": "20240103", "nav": 1.1},
            ],
            "drawdown_curve": [{"trade_date": "20240103", "drawdown": 0.0}],
            "trade_log": [{"trade_date": "20240102", "side": "buy"}],
            "position_log": [{"trade_date": "20240102"}],
            "selection_log": [{"trade_date": "20240102", "symbols": ["000001.SZ"]}],
        },
        "result_page": {
            "equity_curve": {
                "series": [
                    {"trade_date": "20240101", "nav": 1.0},
                    {"trade_date": "20240103", "nav": 1.1},
                ],
                "artifact": {"url": "/artifacts/demo/equity.svg"},
            },
            "drawdown_curve": {"series": [{"trade_date": "20240103", "drawdown": 0.0}]},
        },
    }

    slimmed = slim_response_data(data)

    assert "trade_log" not in slimmed["backtest"]
    assert slimmed["backtest"]["data_size"]["trade_log_rows"] == 1
    assert slimmed["backtest"]["equity_curve"]["point_count"] == 2
    assert "series" not in slimmed["result_page"]["equity_curve"]
    assert slimmed["result_page"]["equity_curve"]["artifact"]["url"] == "/artifacts/demo/equity.svg"
    assert slimmed["result_page"]["equity_curve"]["meta"]["start_date"] == "20240101"

    calls = slim_tool_calls([{"name": "run_backtest", "payload": {"ok": True, "data": data["backtest"]}}])
    assert "trade_log" not in calls[0]["payload"]["data"]
