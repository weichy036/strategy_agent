from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import time
from typing import Any

from strategy_agent.config import settings
from strategy_agent.services.runtime_models import AgentTurnResult


def append_transcript_turn(*, user_id: str, session_id: str, query: str, result: AgentTurnResult) -> None:
    path = _transcript_path(session_id)
    payload = _read_payload(path)
    now = time.time()
    turns = payload.setdefault("turns", [])
    turns.append({"role": "user", "text": query, "timestamp": now})
    turns.append(
        {
            "role": "agent",
            "text": _display_text(result),
            "status": result.status,
            "timestamp": now,
            "data": result.data,
            "timeline": result.timeline,
        }
    )
    payload["session_id"] = session_id
    payload["user_id"] = user_id
    _write_payload(path, payload)


def load_transcript_turns(*, session_id: str, user_id: str) -> list[dict[str, Any]]:
    payload = _read_payload(_transcript_path(session_id))
    if payload.get("user_id") not in {None, user_id}:
        return []
    turns = payload.get("turns")
    return turns if isinstance(turns, list) else []


def delete_transcript(*, session_id: str) -> None:
    path = _transcript_path(session_id)
    if path.exists():
        path.unlink()


def _display_text(result: AgentTurnResult) -> str:
    data = result.data or {}
    result_page = data.get("result_page")
    if isinstance(result_page, dict):
        summary = result_page.get("summary") or {}
        if summary.get("summary_text"):
            return str(summary["summary_text"])
    clarification = data.get("clarification")
    if isinstance(clarification, dict) and clarification.get("next_question"):
        return str(clarification["next_question"])
    return result.assistant_message or "Agent 已响应。"


def _transcript_path(session_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in session_id)
    return settings.artifact_root / safe / "session_transcript.json"


def _read_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"turns": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"turns": []}
    return data if isinstance(data, dict) else {"turns": []}


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return str(value)


__all__ = ["append_transcript_turn", "delete_transcript", "load_transcript_turns"]
