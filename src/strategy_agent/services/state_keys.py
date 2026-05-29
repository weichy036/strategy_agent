"""Centralized ADK session state keys used by Strategy Agent."""


class AgentStateKeys:
    USER_ID = "user_id"
    SESSION_ID = "session_id"
    RUN_ID = "run_id"

    STRATEGY_SCHEMA = "strategy.schema"
    STRATEGY_SCHEMA_DRAFT = "strategy_schema_draft"
    EXECUTABLE_STRATEGY_SCHEMA = "data.executable_strategy_schema"
    DATA_AVAILABILITY = "data.availability"
    WORKFLOW_DATA_READY = "workflow.data_ready"
    BACKTEST_RESULT = "backtest.result"
    METRICS_RESULT = "metrics.result"
    RESULT_PAGE = "report.result_page"

    TOOL_TRACE_BUFFER = "temp:tool_trace_buffer"
    ACTIVE_SUBTASK = "temp:active_subtask"


__all__ = ["AgentStateKeys"]
