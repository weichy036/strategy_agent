from __future__ import annotations

from google.adk.workflow import START, Workflow

from .clarification import create_clarification_agent
from .data_research import create_data_research_agent
from .execution import create_strategy_execution_agent
from .intent_classifier import create_intent_classifier_agent
from .result_explanation import create_result_explanation_agent
from .strategy_designer import create_strategy_designer_agent


def create_research_orchestrator_agent() -> Workflow:
    intent = create_intent_classifier_agent()
    clarification = create_clarification_agent()
    designer = create_strategy_designer_agent()
    data_research = create_data_research_agent()
    execution = create_strategy_execution_agent()
    explanation = create_result_explanation_agent()

    return Workflow(
        name="ResearchOrchestratorAgent",
        description="按顺序编排量化研究工作流的总控 Agent。",
        edges=[(START, intent, clarification, designer, data_research, execution, explanation)],
    )
