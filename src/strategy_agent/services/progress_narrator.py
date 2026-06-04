from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from litellm import completion

from strategy_agent.config import settings
from strategy_agent.services.runtime_models import AdkStreamEvent


CompletionFn = Callable[..., Any]
NARRATED_TOOL_RESULTS = {
    "run_backtest",
    "compute_metrics",
    "assemble_result_page",
}
NARRATED_TOOL_CALLS = {
    "query_market_data",
    "run_backtest",
}
NARRATED_AGENT_MESSAGES = {
    "ClarificationAgent",
    "StrategyDesignerAgent",
    "DataResearchAgent",
}


@dataclass(frozen=True)
class ProgressNarratorAgent:
    """Generate user-facing progress narration from real runtime events."""

    completion_fn: CompletionFn = completion
    max_events: int = 7
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
                max_tokens=110,
                temperature=0.35,
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                api_base=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
                timeout=self.timeout_seconds,
            )
        except Exception:
            return None

        text = _response_text(response)
        if not text or _has_placeholder(text):
            return None
        return text[:180]


def should_narrate(event: AdkStreamEvent, *, phase: str = "after_action") -> bool:
    if phase == "before_action":
        return event.type == "tool_call" and str(event.payload.get("name") or "") in NARRATED_TOOL_CALLS
    if event.type == "tool_result":
        return str(event.payload.get("name") or "") in NARRATED_TOOL_RESULTS
    return event.type == "message" and event.author in NARRATED_AGENT_MESSAGES


def _can_call_model() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def _prompt(*, phase: str, event: AdkStreamEvent, recent_timeline: list[dict[str, Any]]) -> str:
    context = _compact_payload(_narration_context(phase=phase, event=event))
    recent_narrations = _compact_payload(_recent_narrations(recent_timeline))
    timeline = _compact_payload(recent_timeline[-3:])
    return (
        "你是量化回测产品里的 ProgressNarratorAgent。"
        "你的任务是把真实执行进度写成对用户友好的过程叙事，风格类似 Codex。"
        "要求：只输出一句中文；自然、具体、克制；尽量使用第一人称；不要使用 Markdown；"
        "不要编造事件里没有的事实；不要暴露 Python 类名、JSON、token 或内部字段；"
        "不要展示内部流程判断，例如是否继续提问、是否使用系统配置、结构检查等后台决策；"
        "如果条件足够，只说关键条件已确认、可以继续整理方案，不要解释后台为什么这么判断；"
        "不要猜测下一步的参数、起止日期或收益；如果事件内容不足，只说明当前步骤的目的或完成状态；"
        "不要逐点复述收益曲线，只提炼是否完成、覆盖范围、记录数量或关键指标；"
        "不要写成验收报告，不要使用“某某Agent已完成”这种句式；"
        "避免连续使用相同开头，尤其不要连续使用“我已经”；"
        "句式可以在“我先...”“这里的关键是...”“接下来...”“结果里值得注意的是...”之间自然变化；"
        "像在陪用户一起推进任务：说明我正在做什么、为什么这样做、刚发现了什么，或下一步为什么可以继续。"
        f"\n阶段: {phase}"
        f"\n叙事上下文: {context}"
        f"\n最近已展示给用户的叙事: {recent_narrations}"
        f"\n最近轨迹: {timeline}"
    )


def _recent_narrations(recent_timeline: list[dict[str, Any]], limit: int = 4) -> list[str]:
    texts = [
        str(item.get("message") or "").strip()
        for item in recent_timeline
        if item.get("event_type") == "narration" and str(item.get("message") or "").strip()
    ]
    return texts[-limit:]


def _narration_context(*, phase: str, event: AdkStreamEvent) -> dict[str, Any]:
    payload = _event_payload_for_prompt(event)
    name = str(payload.get("name") or "")
    base = {
        "phase": "行动前说明" if phase == "before_action" else "行动后说明",
        "stage": _stage_label(event, name),
        "goal": _stage_goal(event, name),
        "why_it_matters": _stage_reason(event, name),
        "evidence": _stage_evidence(event, name, payload),
        "next_step": _stage_next_step(event, name, payload),
    }
    return {key: value for key, value in base.items() if value}


def _stage_label(event: AdkStreamEvent, name: str) -> str:
    if name == "query_market_data":
        return "检查本地数据"
    if name == "run_backtest":
        return "执行回测"
    if name == "compute_metrics":
        return "整理关键指标"
    if name == "assemble_result_page":
        return "生成结果页"
    return {
        "ClarificationAgent": "确认需求是否完整",
        "StrategyDesignerAgent": "整理策略方案",
        "DataResearchAgent": "核对数据和因子",
    }.get(event.author, "推进回测任务")


def _stage_goal(event: AdkStreamEvent, name: str) -> str:
    if event.type == "tool_call":
        return {
            "query_market_data": "我先确认本地行情和因子数据能否支撑这个策略，避免后面跑出缺字段或空结果。",
            "run_backtest": "我准备把已经确认的策略方案交给回测引擎，生成净值、交易和持仓变化。",
        }.get(name, "")
    return {
        "ClarificationAgent": "确认用户给出的关键交易条件是否足够继续。",
        "StrategyDesignerAgent": "把自然语言里的选股范围、排序规则、持有周期和调仓频率整理成可执行策略。",
        "DataResearchAgent": "检查本地数据覆盖、因子字段和可用交易日，确认策略是否能直接执行。",
        "run_backtest": "回测引擎已经按策略规则跑完，重点看净值点数和交易记录是否有效。",
        "compute_metrics": "把净值序列压缩成用户能判断方向的收益、回撤和夏普等指标。",
        "assemble_result_page": "把结果整理成页面需要的摘要、图表和日志入口。",
    }.get(event.author if event.type == "message" else name, "")


def _stage_reason(event: AdkStreamEvent, name: str) -> str:
    if name == "query_market_data":
        return "数据检查决定这次能不能真实回测，而不是只给示例答案。"
    if name == "run_backtest":
        return "只有跑出净值和交易日志，后面的指标才有意义。"
    if name == "compute_metrics":
        return "用户最终需要快速判断收益、波动和回撤是否值得继续研究。"
    if event.author == "ClarificationAgent":
        return "把注意力放在影响回测含义的关键条件上。"
    return ""


def _stage_evidence(event: AdkStreamEvent, name: str, payload: dict[str, Any]) -> dict[str, Any] | str:
    if event.type == "tool_call":
        return {}
    if name == "run_backtest":
        summary = payload.get("summary") or {}
        return {
            "date_range": payload.get("date_range"),
            "equity_curve_points": payload.get("equity_curve_points"),
            "trade_log_rows": payload.get("trade_log_rows"),
            "selection_log_rows": payload.get("selection_log_rows"),
            "trade_count": summary.get("trade_count"),
        }
    if name == "compute_metrics":
        returns = payload.get("return_metrics") or {}
        risk = payload.get("risk_metrics") or {}
        return {
            "annualized_return": returns.get("annualized_return"),
            "total_return": returns.get("total_return"),
            "max_drawdown": risk.get("max_drawdown"),
            "sharpe": risk.get("sharpe"),
        }
    if name == "assemble_result_page":
        return payload.get("summary") or {}
    if event.author in NARRATED_AGENT_MESSAGES:
        return _compact_payload(payload, limit=700)
    return {}


def _stage_next_step(event: AdkStreamEvent, name: str, payload: dict[str, Any]) -> str:
    if event.type == "tool_call":
        return "等待这一步返回后，我会根据结果决定继续回测、计算指标，或提示需要补数据。"
    if event.author == "ClarificationAgent":
        return "关键条件确认后，就继续整理策略方案。"
    if event.author == "StrategyDesignerAgent":
        return "接下来检查本地数据是否覆盖这个策略需要的标的和因子。"
    if event.author == "DataResearchAgent":
        return "如果数据可用，就进入确定性的回测执行链路。"
    if name == "run_backtest":
        return "接下来把净值和交易记录整理成关键收益指标。"
    if name == "compute_metrics":
        return "接下来把指标、收益曲线和日志入口整理到结果页。"
    return ""


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


def _has_placeholder(text: str) -> bool:
    return bool(re.search(r"(?:X%|Y%|Z%|N个月|20XX|XX年|某个因子)", text))


__all__ = ["ProgressNarratorAgent", "should_narrate"]
