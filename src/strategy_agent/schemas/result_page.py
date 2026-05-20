from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResultPage(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    metric_cards: dict[str, Any] = Field(default_factory=dict)
    equity_curve: dict[str, Any] = Field(default_factory=dict)
    drawdown_curve: dict[str, Any] = Field(default_factory=dict)
    trade_stats: dict[str, Any] = Field(default_factory=dict)
    risk_disclosures: list[str] = Field(default_factory=list)
