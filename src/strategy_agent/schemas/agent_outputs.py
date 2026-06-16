from __future__ import annotations

from typing import Any, Literal

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
    inferred_fields: dict[str, Any] = Field(default_factory=dict)
    reason: str


class ConversationContextOutput(BaseModel):
    turn_type: Literal[
        "new_strategy",
        "strategy_revision",
        "result_follow_up",
        "general_chat",
        "unsupported",
    ]
    confidence: float = Field(ge=0, le=1)
    should_inherit_previous_strategy: bool
    rewritten_query: str = Field(
        description="把当前用户输入和必要历史上下文合并后的中文任务描述。新策略时可等于当前用户输入。"
    )
    revision_summary: str | None = Field(
        default=None,
        description="如果是修改上一轮策略，用一句话说明本轮修改了什么。",
    )
    base_strategy_summary: str | None = Field(
        default=None,
        description="如果继承上一轮策略，用一句话概括被继承的策略。",
    )
    patch_hints: dict[str, Any] = Field(
        default_factory=dict,
        description="模型识别出的修改提示，例如 portfolio.position_count=10；仅作为后续 Agent 的上下文，不由代码直接套规则。",
    )
    rationale: str


class ClarificationOutput(BaseModel):
    needs_clarification: bool
    next_question: str | None = Field(
        default=None,
        description="One concise Chinese question when clarification is required.",
    )
    must_ask_fields: list[str] = Field(
        default_factory=list,
        description="Fields that block safe backtesting and must be answered by the user.",
    )
    defaultable_fields: list[str] = Field(
        default_factory=list,
        description="Missing fields that should use project defaults instead of asking the user.",
    )
    resolved_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Fields already resolved from the conversation.",
    )
    rationale: str


class ResultExplanationOutput(BaseModel):
    summary_text: str
    risk_text: str
    limitations_text: str
    equity_curve_commentary: str
    follow_up_suggestions: list[str] = Field(default_factory=list)
