from __future__ import annotations

from google.adk import Agent
from google.adk.tools.agent_tool import AgentTool

from strategy_agent.config import settings
from strategy_agent.services.agent_trace import (
    after_tool_trace,
    before_tool_trace,
    on_tool_error_trace,
)
from .clarification import create_clarification_agent
from .intent_classifier import create_intent_classifier_agent
from .result_explanation import create_result_explanation_agent
from .strategy_designer import create_strategy_designer_agent
from strategy_agent.tools import (
    assemble_result_page,
    compute_metrics,
    query_market_data,
    resolve_instrument_tool,
    run_backtest,
    store_artifact,
    validate_strategy_schema,
)


def create_research_orchestrator_agent() -> Agent:
    intent_agent = create_intent_classifier_agent()
    clarification_agent = create_clarification_agent()
    designer_agent = create_strategy_designer_agent()
    explanation_agent = create_result_explanation_agent()
    return Agent(
        name="ResearchOrchestratorAgent",
        model=settings.adk_model,
        description="Top-level orchestrator for natural-language quant research workflows.",
        instruction=(
            "You are the root orchestrator for a multi-turn quant research workflow. "
            "Use AgentTool-wrapped specialist agents for intent classification, clarification, "
            "strategy design, and result explanation. "
            "Never rely on hardcoded parsing rules. "
            "When strategy information is incomplete, ask concise clarification questions first. "
            "Treat every new user message in the same session as continuation context. "
            "Do not ask for already provided information unless conflicting. "
            "Expose progress by calling the relevant specialist agent or tool for each stage. "
            "When complete, produce Strategy Schema JSON and execute tools in order: "
            "validate_strategy_schema -> run_backtest -> compute_metrics -> assemble_result_page. "
            "The final result is incomplete unless assemble_result_page contains an equity_curve series. "
            "Always summarize assumptions and risk limitations. "
            "For clarification turns, prefer one focused question per turn in Chinese."
        ),
        tools=[
            AgentTool(intent_agent),
            AgentTool(clarification_agent),
            AgentTool(designer_agent),
            AgentTool(explanation_agent),
            resolve_instrument_tool,
            validate_strategy_schema,
            query_market_data,
            run_backtest,
            compute_metrics,
            store_artifact,
            assemble_result_page,
        ],
        before_tool_callback=before_tool_trace,
        after_tool_callback=after_tool_trace,
        on_tool_error_callback=on_tool_error_trace,
        output_key="orchestrator_result",
    )
