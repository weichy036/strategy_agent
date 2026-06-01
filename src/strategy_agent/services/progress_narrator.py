from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from litellm import completion

from strategy_agent.config import settings
from strategy_agent.services.runtime_models import AdkStreamEvent


CompletionFn = Callable[..., Any]
NARRATED_TOOL_RESULTS = {
    "query_market_data",
    "run_backtest",
    "compute_metrics",
    "assemble_result_page",
}
NARRATED_AGENT_MESSAGES = {
    "ClarificationAgent",
    "StrategyDesignerAgent",
    "DataResearchAgent",
    "ResultExplanationAgent",
}


@dataclass(frozen=True)
class ProgressNarratorAgent:
    """Generate user-facing progress narration from real runtime events."""

    completion_fn: CompletionFn = completion
    max_events: int = 8
    timeout_seconds: int = 8

    def narrate(self, *, phase: str, event: AdkStreamEvent, recent_timeline: list[dict[str, Any]] | None = None) -> str | None:
        if not _can_call_model():
            return None

        prompt = _prompt(
            phase=phase,
            event=event,
            recent_timeline=recent_timeline or [],
        )
        try:
            response = self.completion_fn(
                model=settings.adk_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=90,
                temperature=0.2,
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                api_base=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
                timeout=self.timeout_seconds,
            )
        except Exception:
            return None

        text = _response_text(response)
        if not text:
            return None
        return text[:180]


def should_narrate(event: AdkStreamEvent) -> bool:
    if event.type == "tool_result":
        return str(event.payload.get("name") or "") in NARRATED_TOOL_RESULTS
    return event.type == "message" and event.author in NARRATED_AGENT_MESSAGES


def _can_call_model() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def _prompt(*, phase: str, event: AdkStreamEvent, recent_timeline: list[dict[str, Any]]) -> str:
    payload = _compact_payload(_event_payload_for_prompt(event))
    timeline = _compact_payload(recent_timeline[-3:])
    return (
        "你是量化回测产品里的 ProgressNarratorAgent。"
        "你的任务是把真实执行事件转成对用户友好的过程叙事，风格类似 Codex。"
        "要求：只输出一句中文；自然、具体、克制；不要使用 Markdown；"
        "不要编造事件里没有的事实；不要暴露 Python 类名、JSON、token 或内部字段；"
        "不要猜测下一步的参数、起止日期或收益；如果事件内容不足，只说明当前步骤的目的或完成状态；"
        "不要逐点复述收益曲线，只提炼是否完成、覆盖范围、记录数量或关键指标；"
        "说明这一步已经完成了什么、得到什么关键结论，或为什么接下来可以继续。"
        f"\n阶段: {phase}"
        f"\n事件类型: {event.type}"
        f"\n事件来源: {event.author}"
        f"\n事件内容: {payload}"
        f"\n最近轨迹: {timeline}"
    )


def _event_payload_for_prompt(event: AdkStreamEvent) -> dict[str, Any]:
    payload = event.payload or {}
    if event.type == "tool_call":
        name = str(payload.get("name") or "")
        return {
            "name": name,
            "args": payload.get("args") or {},
            "domain_note": _domain_note(name),
        }
    if event.type != "tool_result":
        return payload

    name = str(payload.get("name") or "")
    response = _tool_response(payload.get("response"))
    data = response.get("data") if isinstance(response, dict) else None
    base = {
        "name": name,
        "ok": response.get("ok") if isinstance(response, dict) else None,
        "error": response.get("error") if isinstance(response, dict) else None,
        "domain_note": _domain_note(name),
    }
    if not isinstance(data, dict):
        return base
    if name == "run_backtest":
        return {
            **base,
            "run_id": data.get("run_id"),
            "date_range": data.get("date_range"),
            "summary": data.get("summary"),
            "equity_curve_points": len(data.get("equity_curve") or []),
            "trade_log_rows": len(data.get("trade_log") or []),
            "selection_log_rows": len(data.get("selection_log") or []),
        }
    if name == "compute_metrics":
        return {
            **base,
            "return_metrics": data.get("return_metrics"),
            "risk_metrics": data.get("risk_metrics"),
            "yearly_returns": (data.get("period_breakdown") or {}).get("yearly_returns"),
        }
    if name == "assemble_result_page":
        summary = ((data.get("result_page") or {}).get("summary") or {})
        return {**base, "summary": summary}
    return {**base, "data": data}


def _tool_response(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("result"), dict):
        return value["result"]
    return value if isinstance(value, dict) else {}


def _domain_note(name: str) -> str:
    if name == "query_market_data":
        return "latest_trade_date 表示本地最新可用交易日，通常用于数据检查或默认结束日期，不代表回测起点。"
    return ""


def _compact_payload(value: Any, limit: int = 2200) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _response_text(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except Exception:
        return ""
    return str(content or "").strip().strip('"').strip()


__all__ = ["ProgressNarratorAgent", "should_narrate"]
