from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from google.adk.models.registry import LLMRegistry
from pydantic import BaseModel, Field

from strategy_agent.config import settings
from strategy_agent.services.agent_runtime import get_agent_runtime


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

    return app


app = create_api_app()


def main() -> None:
    import uvicorn

    uvicorn.run("strategy_agent.api:app", host="0.0.0.0", port=8000, reload=False)
