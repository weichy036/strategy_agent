from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IntentClassificationOutput(BaseModel):
    intent_type: Literal[
        "single_instrument_backtest",
        "cross_sectional_backtest",
        "strategy_explanation",
        "unsupported",
        "general_chat",
    ]
    confidence: float = Field(ge=0, le=1)
    is_backtest_request: bool
    is_backtestable_now: bool
    missing_fields: list[str] = Field(default_factory=list)
    inferred_fields: dict[str, str] = Field(default_factory=dict)
    reason: str


class ClarificationOutput(BaseModel):
    needs_clarification: bool
    next_question: str | None = None
    must_ask_fields: list[str] = Field(default_factory=list)
    defaultable_fields: list[str] = Field(default_factory=list)
    resolved_fields: dict[str, str] = Field(default_factory=dict)
    rationale: str


class ResultExplanationOutput(BaseModel):
    summary_text: str
    risk_text: str
    limitations_text: str
    equity_curve_commentary: str
    follow_up_suggestions: list[str] = Field(default_factory=list)
