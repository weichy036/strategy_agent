from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from strategy_agent.services.observability import build_observability
from strategy_agent.services.runtime_models import AdkStreamEvent, AgentTurnResult
from strategy_agent.services.structured_outputs import AGENT_OUTPUT_SCHEMAS, parse_agent_output
AGENT_OUTPUT_DATA_KEYS = {
    "IntentClassifierAgent": "intent",
    "ClarificationAgent": "clarification",
    "StrategyDesignerAgent": "strategy_schema",
    "DataResearchAgent": "data_availability",
    "ResultExplanationAgent": "explanations",
}


def timeline_entry(
    *,
    event_type: str,
    actor: str,
    status: str,
    message: str,
    stage: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "actor": actor,
        "status": status,
        "stage": stage or actor,
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }


class StrategyRunResultCollector:
    """Collect adapted ADK events into the API response shape."""

    def __init__(self) -> None:
        self.status = "assistant_response"
        self.assistant_messages: list[str] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.timeline: list[dict[str, Any]] = []
        self.result_data: dict[str, Any] = {}
        self.usage_items: list[dict[str, Any]] = []
        self._seen_state_trace_keys: set[tuple[str, str, str, str | None]] = set()

    def record(self, event: AdkStreamEvent) -> None:
        handler = {
            "tool_call": self._record_tool_call,
            "tool_result": self._record_tool_result,
            "message": self._record_message,
            "state_trace": self._record_state_trace,
            "usage": self._record_usage,
            "error": self._record_error,
        }.get(event.type)
        if handler:
            handler(event)

    def build(self) -> AgentTurnResult:
        self._promote_completed_result()
        self._apply_result_gate()
        assistant_message = "\n".join([item for item in self.assistant_messages if item]).strip()
        self._apply_clarification_status(assistant_message)
        usage = self._usage_summary()
        data = {**self.result_data, "usage": usage}
        data["observability"] = build_observability(
            timeline=self.timeline,
            usage=usage,
            result_data=self.result_data,
            status=self.status,
        )
        return AgentTurnResult(
            status=self.status,
            assistant_message=assistant_message,
            data=data,
            tool_calls=self.tool_calls,
            timeline=self.timeline,
        )

    def has_completed_result(self) -> bool:
        result_page = self.result_data.get("result_page")
        if not isinstance(result_page, dict):
            return False
        equity_series = (result_page.get("equity_curve") or {}).get("series")
        return self.status == "completed" and bool(equity_series)

    def _apply_clarification_status(self, assistant_message: str) -> None:
        clarification = self.result_data.get("clarification")
        if isinstance(clarification, dict) and clarification.get("needs_clarification"):
            self.status = "needs_clarification"
            clarification.setdefault("next_question", assistant_message or "需要补充关键信息后再执行回测。")

        intent = self.result_data.get("intent")
        if isinstance(intent, dict) and intent.get("is_backtest_request") is False and (self.result_data.get("explanations") or assistant_message):
            if "explanations" not in self.result_data:
                self.result_data["explanations"] = {"summary_text": assistant_message or "我可以帮助你把自然语言策略转成可回测的研究流程。"}
            self.status = "answered"
            return

        data_availability = self.result_data.get("data_availability")
        if self.status != "completed" and isinstance(data_availability, dict) and data_availability.get("is_ready") is False:
            self.status = "blocked_missing_data"
            return

        validation = self.result_data.get("validation")
        if self.status != "completed" and isinstance(validation, dict) and validation.get("is_complete") is False:
            self.status = "needs_clarification"

        if self.status == "needs_clarification" and "clarification" not in self.result_data:
            self.result_data["clarification"] = {
                "next_question": assistant_message or "需要补充关键信息后再执行回测。",
                "must_ask_fields": [],
            }

    def _record_tool_call(self, event: AdkStreamEvent) -> None:
        name = str(event.payload.get("name") or "unknown_tool")
        self.timeline.append(timeline_entry(event_type="tool_start", actor=name, status="running", message=f"{name} 开始执行"))

    def _record_tool_result(self, event: AdkStreamEvent) -> None:
        name = str(event.payload.get("name") or "")
        payload = _tool_payload(event.payload.get("response"))
        ok = payload.get("ok") if isinstance(payload, dict) else None
        status = "success" if ok is True else "error" if ok is False else "done"
        self.timeline.append(timeline_entry(event_type="tool_done", actor=name, status=status, message=f"{name} 执行完成"))
        self.tool_calls.append({"name": name, "payload": payload})
        self._store_parsed_agent_output(name=name, payload=payload)
        if not isinstance(payload, dict):
            return
        self._store_tool_data(name, payload)

    def _record_message(self, event: AdkStreamEvent) -> None:
        text = str(event.payload.get("text") or "")
        if not text:
            return
        if event.author in AGENT_OUTPUT_SCHEMAS:
            parsed_ok = self._store_parsed_agent_output(name=event.author, payload=text)
            if not parsed_ok and event.author == "ResultExplanationAgent":
                self.assistant_messages.append(text)
            return
        self.assistant_messages.append(text)

    def _record_error(self, event: AdkStreamEvent) -> None:
        message = str(event.payload.get("message") or event.payload.get("code") or "ADK error")
        self.timeline.append(timeline_entry(event_type="adk_error", actor=event.author, status="error", message=message))

    def _record_usage(self, event: AdkStreamEvent) -> None:
        usage = _normalize_usage(event.payload)
        usage["actor"] = event.author
        self.usage_items.append(usage)
        self.timeline.append(
            timeline_entry(
                event_type="token_usage",
                actor=event.author,
                status="success",
                message=f"tokens {usage['total_tokens']} (in {usage['prompt_tokens']} / out {usage['completion_tokens']})",
            )
        )

    def _record_state_trace(self, event: AdkStreamEvent) -> None:
        item = event.payload
        key = (
            str(item.get("event_type") or "trace"),
            str(item.get("actor") or event.author),
            str(item.get("message") or ""),
            item.get("timestamp"),
        )
        if key in self._seen_state_trace_keys:
            return
        self._seen_state_trace_keys.add(key)
        self.timeline.append(
            {
                "event_type": item.get("event_type", "trace"),
                "actor": item.get("actor", event.author),
                "status": item.get("status", "done"),
                "stage": item.get("stage") or item.get("actor", event.author),
                "message": item.get("message", ""),
                "timestamp": item.get("timestamp"),
            }
        )

    def _store_parsed_agent_output(self, *, name: str, payload: Any) -> bool:
        parsed = parse_agent_output(name, payload)
        if parsed is None:
            return False

        if parsed.ok and parsed.data is not None:
            data_key = AGENT_OUTPUT_DATA_KEYS.get(name)
            if data_key:
                self.result_data[data_key] = parsed.data
            self.timeline.append(
                timeline_entry(
                    event_type="agent_output_parsed",
                    actor=name,
                    status="success",
                    stage=name,
                    message=f"{name} 结构化输出校验通过",
                )
            )
            return True

        self.timeline.append(
            timeline_entry(
                event_type="agent_output_parse_failed",
                actor=name,
                status="error",
                stage=name,
                message=f"{name} 结构化输出校验失败：{parsed.error}",
            )
        )
        return False

    def _store_tool_data(self, name: str, payload: dict[str, Any]) -> None:
        if name == "validate_strategy_schema":
            self.result_data["validation"] = payload.get("data")
            if payload.get("ok") and isinstance(payload.get("data"), dict) and not payload["data"].get("is_complete"):
                self.status = "needs_clarification"
        elif name == "run_backtest" and payload.get("ok"):
            self.result_data["backtest"] = payload.get("data")
        elif name == "compute_metrics" and payload.get("ok"):
            self.result_data["metrics"] = payload.get("data")
        elif name == "assemble_result_page" and payload.get("ok"):
            self.result_data["result_page"] = (payload.get("data") or {}).get("result_page")
            self.status = "completed"

    def _apply_result_gate(self) -> None:
        result_page = self.result_data.get("result_page")
        equity_series = None
        if isinstance(result_page, dict):
            equity_series = (result_page.get("equity_curve") or {}).get("series")
        if self.status == "completed" and not equity_series:
            self.status = "blocked_missing_equity_curve"
            self.timeline.append(
                timeline_entry(
                    event_type="result_blocked",
                    actor="ResultGate",
                    status="error",
                    stage="result_page",
                    message="结果页缺少收益曲线，不能标记为完成",
                )
            )

    def _promote_completed_result(self) -> None:
        result_page = self.result_data.get("result_page")
        if not isinstance(result_page, dict):
            return
        equity_series = (result_page.get("equity_curve") or {}).get("series")
        if equity_series:
            self.status = "completed"

    def _usage_summary(self) -> dict[str, Any]:
        totals = {
            "prompt_tokens": sum(item["prompt_tokens"] for item in self.usage_items),
            "completion_tokens": sum(item["completion_tokens"] for item in self.usage_items),
            "total_tokens": sum(item["total_tokens"] for item in self.usage_items),
        }
        return {"total": totals, "items": self.usage_items}


def _short_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}..."


def _tool_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and "result" in payload and isinstance(payload["result"], dict):
        return payload["result"]
    return payload


def _normalize_usage(payload: dict[str, Any]) -> dict[str, int]:
    def pick(*names: str) -> int:
        for name in names:
            value = payload.get(name)
            if isinstance(value, int | float):
                return int(value)
        return 0

    prompt = pick("prompt_token_count", "prompt_tokens")
    completion = pick("candidates_token_count", "completion_tokens")
    total = pick("total_token_count", "total_tokens") or prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


__all__ = ["StrategyRunResultCollector", "timeline_entry"]
