from __future__ import annotations

from google.adk.agents import SequentialAgent

from .clarification import create_clarification_agent
from .data_research import create_data_research_agent
from .execution import create_strategy_execution_agent
from .intent_classifier import create_intent_classifier_agent
from .result_explanation import create_result_explanation_agent
from .strategy_designer import create_strategy_designer_agent


def create_research_orchestrator_agent() -> SequentialAgent:
    return SequentialAgent(
        name="ResearchOrchestratorAgent",
        description="按顺序编排量化研究工作流的总控 Agent。",
        sub_agents=[
            create_intent_classifier_agent(),
            create_clarification_agent(),
            create_strategy_designer_agent(),
            create_data_research_agent(),
            create_strategy_execution_agent(),
            create_result_explanation_agent(),
        ],
    )
