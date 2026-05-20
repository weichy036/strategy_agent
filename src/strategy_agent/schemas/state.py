from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClarificationState(BaseModel):
    needed: bool = False
    must_ask_fields: list[str] = Field(default_factory=list)
    defaultable_fields: list[str] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)
    resolved_fields: list[str] = Field(default_factory=list)
    defaulted_fields: list[str] = Field(default_factory=list)


class StrategyState(BaseModel):
    draft: dict[str, Any] = Field(default_factory=dict)
    card: dict[str, Any] = Field(default_factory=dict)
    schema_data: dict[str, Any] = Field(default_factory=dict, alias="schema")
    strategy_id: str | None = None
    is_ready: bool = False


class BacktestState(BaseModel):
    status: str = "idle"
    run_id: str | None = None
    date_range: dict[str, str] | None = None
    summary: dict[str, Any] | None = None
    metrics_ready: bool = False


class ResultState(BaseModel):
    summary_text: str | None = None
    risk_text: str | None = None
    limitations_text: str | None = None
    result_page_ready: bool = False


class ArtifactRefs(BaseModel):
    strategy_draft: str | None = None
    strategy_card: str | None = None
    strategy_schema: str | None = None
    backtest_result: str | None = None
    equity_curve: str | None = None
    drawdown_curve: str | None = None
    report: str | None = None


class SessionWorkflowState(BaseModel):
    workflow_version: str = "v1"
    current_query: str = ""
    problem_type: str | None = None
    stage: str = "intake"
    clarification: ClarificationState = Field(default_factory=ClarificationState)
    strategy: StrategyState = Field(default_factory=StrategyState)
    backtest: BacktestState = Field(default_factory=BacktestState)
    result: ResultState = Field(default_factory=ResultState)
    artifacts: ArtifactRefs = Field(default_factory=ArtifactRefs)
    context: dict[str, Any] = Field(default_factory=dict)
