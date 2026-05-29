from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.models.registry import LLMRegistry
from pydantic import BaseModel, Field

from strategy_agent.config import settings
from strategy_agent.services.adk_event_adapter import adapt_adk_event, extract_text_from_content
from strategy_agent.services.agent_runtime import get_agent_runtime
from strategy_agent.services.result_collector import StrategyRunResultCollector


def _mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "***"
    return f"{value[:6]}***{value[-4:]}"


def _build_base_status() -> dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    model = settings.adk_model
    registry_class = None
    registry_error = None
    try:
        registry_class = LLMRegistry.resolve(model).__name__
    except Exception as exc:  # noqa: BLE001
        registry_error = str(exc)

    return {
        "configured_model": model,
        "llm_registry_class": registry_class,
        "llm_registry_error": registry_error,
        "api_base": api_base,
        "api_key_present": bool(api_key),
        "api_key_hint": _mask_secret(api_key),
    }


def _probe_deepseek_model() -> dict[str, Any]:
    model = settings.adk_model
    api_key = os.getenv("DEEPSEEK_API_KEY")
    api_base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    if not api_key:
        return {
            "reachable": False,
            "error": "DEEPSEEK_API_KEY is not set",
        }
    try:
        from litellm import completion

        response = completion(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0,
            api_key=api_key,
            api_base=api_base,
            timeout=12,
        )
        response_model = getattr(response, "model", None)
        usage = getattr(response, "usage", None)
        return {
            "reachable": True,
            "response_model": response_model,
            "usage": usage.model_dump() if hasattr(usage, "model_dump") else str(usage),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "reachable": False,
            "error": str(exc),
        }


class ResearchRunRequest(BaseModel):
    query: str = Field(..., description="Natural-language strategy research query")
    user_id: str = Field(default="web-user", description="User id used for ADK session continuity")
    session_id: str = Field(default="api", description="Session identifier for artifact storage")


class ResearchRunResponse(BaseModel):
    ok: bool
    status: str | None = None
    error_code: str | None = None
    message: str | None = None
    assistant_message: str | None = None
    data: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    timeline: list[dict[str, Any]] | None = None
    meta: dict[str, Any] | None = None


class SessionTurn(BaseModel):
    role: str
    text: str
    status: str | None = None
    timestamp: float | None = None
    data: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] | None = None


class SessionHistoryResponse(BaseModel):
    session_id: str
    user_id: str
    turns: list[SessionTurn]
    state: dict[str, Any]


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _session_turns(session) -> list[SessionTurn]:
    grouped: dict[str, list[Any]] = {}
    for event in session.events:
        grouped.setdefault(event.invocation_id or event.id, []).append(event)

    turns: list[SessionTurn] = []
    for events in grouped.values():
        user_text = _first_user_text(events)
        if user_text:
            turns.append(SessionTurn(role="user", text=user_text, timestamp=events[0].timestamp))

        assistant = _assistant_turn(events)
        if assistant:
            turns.append(assistant)
    return turns


def _first_user_text(events: list[Any]) -> str | None:
    for event in events:
        content = getattr(event, "content", None)
        if getattr(content, "role", None) != "user":
            continue
        text = extract_text_from_content(content).strip()
        if text:
            return text
    return None


def _assistant_turn(events: list[Any]) -> SessionTurn | None:
    collector = StrategyRunResultCollector()
    for event in events:
        for adapted_event in adapt_adk_event(event):
            collector.record(adapted_event)
    result = collector.build()
    message = _display_assistant_message(result)
    if not message:
        return None
    return SessionTurn(
        role="agent",
        text=message,
        status=result.status,
        timestamp=events[-1].timestamp if events else None,
        data=result.data or None,
        timeline=result.timeline or None,
    )


def _display_assistant_message(result) -> str:
    data = result.data or {}
    result_page = data.get("result_page")
    if isinstance(result_page, dict):
        summary = result_page.get("summary") or {}
        if summary.get("summary_text"):
            return str(summary["summary_text"])

    clarification = data.get("clarification")
    if isinstance(clarification, dict) and clarification.get("next_question"):
        return str(clarification["next_question"])

    explanations = data.get("explanations")
    if isinstance(explanations, dict) and explanations.get("summary_text"):
        return str(explanations["summary_text"])

    if result.status == "blocked_missing_data":
        availability = data.get("data_availability") or {}
        issues = availability.get("blocking_issues") or []
        return "数据暂未就绪：" + ("；".join(issues) if issues else str(availability.get("rationale") or "缺少本地数据。"))

    message = (result.assistant_message or "").strip()
    if message.startswith("{") or message.startswith("["):
        return ""
    return message


def create_api_app() -> FastAPI:
    app = FastAPI(
        title="Strategy Agent API",
        description="Health and model diagnostics for Strategy Agent.",
        version="0.1.0",
    )
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_model=None)
    def index():
        index_file = static_dir / "index.html"
        if not index_file.exists():
            return PlainTextResponse("static/index.html not found", status_code=404)
        return FileResponse(index_file, media_type="text/html")

    @app.get("/artifacts/{session_id}/{artifact_name}", response_model=None)
    def artifact_file(session_id: str, artifact_name: str):
        artifact_path = (settings.artifact_root / session_id / unquote(artifact_name)).resolve()
        artifact_root = settings.artifact_root.resolve()
        if artifact_root not in artifact_path.parents or not artifact_path.exists():
            return PlainTextResponse("artifact not found", status_code=404)
        media_type = "image/svg+xml" if artifact_path.suffix == ".svg" else "application/json"
        return FileResponse(artifact_path, media_type=media_type)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "strategy-agent"}

    @app.get("/health/model")
    def health_model(
        check: int = Query(
            default=0,
            description="Set to 1 to perform an online probe to DeepSeek API.",
        ),
    ) -> dict[str, Any]:
        status = _build_base_status()
        if check == 1:
            status["probe"] = _probe_deepseek_model()
        else:
            status["probe"] = {
                "reachable": None,
                "skipped": True,
                "reason": "check=0 (configuration-only inspection)",
            }
        return status

    @app.get("/research/examples")
    def research_examples() -> dict[str, list[str]]:
        return {
            "examples": [
                "对于沪深300ETF，MACD 日线金叉买入、死叉卖出，每年的平均收益是多少？",
                "MACD 金叉买入效果怎么样？",
                "如果每个月买入市值最大的20只股票，持有到下个月，收益是多少？",
            ]
        }

    @app.get("/research/session/{session_id}/history", response_model=SessionHistoryResponse)
    async def research_session_history(
        session_id: str,
        user_id: str = Query(default="web-user"),
    ) -> SessionHistoryResponse:
        runtime = get_agent_runtime()
        session = await runtime.runner.session_service.get_session(
            app_name=runtime.runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if session is None:
            return SessionHistoryResponse(session_id=session_id, user_id=user_id, turns=[], state={})
        return SessionHistoryResponse(
            session_id=session.id,
            user_id=session.user_id,
            turns=_session_turns(session),
            state=session.state,
        )

    @app.post("/research/run", response_model=ResearchRunResponse)
    def research_run(payload: ResearchRunRequest) -> ResearchRunResponse:
        try:
            runtime = get_agent_runtime()
            turn = runtime.run_turn(
                user_id=payload.user_id,
                session_id=payload.session_id,
                message=payload.query,
            )
            return ResearchRunResponse(
                ok=True,
                status=turn.status,
                assistant_message=turn.assistant_message,
                data=turn.data,
                tool_calls=turn.tool_calls,
                timeline=turn.timeline,
                meta={
                    "mode": "agent_full_workflow",
                    "model": settings.adk_model,
                    "user_id": payload.user_id,
                    "session_id": payload.session_id,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ResearchRunResponse(
                ok=False,
                status="error",
                error_code="agent_run_failed",
                message=str(exc),
                assistant_message=None,
                data=None,
                tool_calls=[],
                timeline=[],
                meta={"mode": "agent_full_workflow", "model": settings.adk_model},
            )

    @app.post("/research/stream", response_model=None)
    async def research_stream(payload: ResearchRunRequest) -> StreamingResponse:
        async def event_generator():
            runtime = get_agent_runtime()
            try:
                async for event in runtime.stream_turn(
                    user_id=payload.user_id,
                    session_id=payload.session_id,
                    message=payload.query,
                ):
                    yield _sse(str(event.get("type") or "message"), event)
                yield _sse("done", {"type": "done"})
            except Exception as exc:  # noqa: BLE001
                yield _sse(
                    "error",
                    {
                        "type": "error",
                        "ok": False,
                        "status": "error",
                        "error_code": "agent_stream_failed",
                        "message": str(exc),
                    },
                )

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_api_app()


def main() -> None:
    import uvicorn

    uvicorn.run("strategy_agent.api:app", host="0.0.0.0", port=8000, reload=False)
