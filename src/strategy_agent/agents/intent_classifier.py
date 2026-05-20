from __future__ import annotations

from google.adk import Agent

from strategy_agent.config import settings
from strategy_agent.schemas.agent_outputs import IntentClassificationOutput
from .schema_contracts import json_contract_instruction
from .schema_contracts import output_schema_kwargs


def create_intent_classifier_agent() -> Agent:
    return Agent(
        name="IntentClassifierAgent",
        model=settings.adk_model,
        description="Classifies user research intent and identifies required information.",
        instruction=(
            "Classify the user's request into a quant research intent. "
            "Identify whether the request is backtestable now or requires clarification. "
            "Do not fabricate missing fields; explicitly surface what is missing. "
            f"{json_contract_instruction(IntentClassificationOutput)}"
        ),
        output_key="intent_classification",
        **output_schema_kwargs(IntentClassificationOutput),
    )
