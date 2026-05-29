from __future__ import annotations

from datetime import datetime
from typing import Any


def build_observability(
    *,
    timeline: list[dict[str, Any]],
    usage: dict[str, Any],
    result_data: dict[str, Any],
    status: str,
) -> dict[str, Any]:
    spans = _spans_from_timeline(timeline, usage.get("items") or [])
    backtest = result_data.get("backtest") if isinstance(result_data.get("backtest"), dict) else {}
    return {
        "run_id": backtest.get("run_id") or _fallback_run_id(timeline),
        "status": status,
        "spans": spans,
        "latency_ms": max((span["end_ms"] for span in spans), default=0),
        "usage": usage,
        "cost": {"amount": None, "currency": "USD"},
    }


def _spans_from_timeline(timeline: list[dict[str, Any]], usage_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = [_event(item, index) for index, item in enumerate(timeline)]
    base = next((event["time_ms"] for event in events if event["time_ms"] is not None), None)
    starts: dict[str, dict[str, Any]] = {}
    spans: list[dict[str, Any]] = []

    for event in events:
        offset = _offset(event, base)
        actor = str(event["actor"] or event["stage"] or "Agent")
        event_type = str(event["event_type"] or "")
        if event_type.endswith("_start"):
            starts[actor] = {**event, "offset_ms": offset}
            continue
        if event_type.endswith("_done") and actor in starts:
            start = starts.pop(actor)
            spans.append(_span(actor, event, start["offset_ms"], max(offset - start["offset_ms"], 1)))
            continue
        if not event_type.endswith("_start"):
            spans.append(_span(actor, event, offset, 50))

    for item in usage_items:
        actor = str(item.get("actor") or "LLM")
        if any(span["actor"] == actor and span["type"] == "llm" for span in spans):
            continue
        start_ms = len(spans) * 50
        spans.append(
            {
                "id": f"span_{len(spans) + 1}",
                "actor": actor,
                "name": actor,
                "type": "llm",
                "status": "success",
                "start_ms": start_ms,
                "duration_ms": 50,
                "end_ms": start_ms + 50,
                "tokens": _usage_tokens(item),
                "metadata": {},
            }
        )

    return [_with_id(span, index) for index, span in enumerate(spans)]


def _event(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "index": index,
        "event_type": item.get("event_type"),
        "actor": item.get("actor"),
        "stage": item.get("stage"),
        "status": item.get("status"),
        "message": item.get("message"),
        "timestamp": item.get("timestamp"),
        "time_ms": _parse_time_ms(item.get("timestamp")),
        "raw": item,
    }


def _span(actor: str, event: dict[str, Any], start_ms: int, duration_ms: int) -> dict[str, Any]:
    status = "error" if event["status"] == "error" else "running" if event["status"] == "running" else "success"
    return {
        "actor": actor,
        "name": _display_name(actor),
        "type": _span_type(event),
        "status": status,
        "start_ms": start_ms,
        "duration_ms": duration_ms,
        "end_ms": start_ms + duration_ms,
        "tokens": {},
        "metadata": {
            "event_type": event["event_type"],
            "message": event["message"],
            "stage": event["stage"],
        },
    }


def _span_type(event: dict[str, Any]) -> str:
    event_type = str(event["event_type"] or "")
    actor = str(event["actor"] or event["stage"] or "")
    if event["status"] == "error":
        return "error"
    if event_type == "token_usage" or actor.endswith("Agent"):
        return "llm"
    if "tool" in event_type:
        return "tool"
    return "agent"


def _offset(event: dict[str, Any], base: int | None) -> int:
    if event["time_ms"] is not None and base is not None:
        return max(0, int(event["time_ms"] - base))
    return int(event["index"] * 50)


def _parse_time_ms(value: Any) -> int | None:
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def _fallback_run_id(timeline: list[dict[str, Any]]) -> str:
    first = next((item.get("timestamp") for item in timeline if item.get("timestamp")), None)
    if not first:
        return "run_pending"
    return "run_" + "".join(ch for ch in str(first) if ch.isdigit())[:14]


def _usage_tokens(item: dict[str, Any]) -> dict[str, int]:
    return {
        "prompt_tokens": int(item.get("prompt_tokens") or 0),
        "completion_tokens": int(item.get("completion_tokens") or 0),
        "total_tokens": int(item.get("total_tokens") or 0),
    }


def _with_id(span: dict[str, Any], index: int) -> dict[str, Any]:
    return {"id": f"span_{index + 1}", **span}


def _display_name(name: str) -> str:
    return {
        "IntentClassifierAgent": "Intent classifier",
        "ClarificationAgent": "Clarification",
        "StrategyDesignerAgent": "Strategy designer",
        "DataResearchAgent": "Data research",
        "ResultExplanationAgent": "Result explanation",
    }.get(name, name)


__all__ = ["build_observability"]
