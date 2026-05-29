from __future__ import annotations

import os
from typing import Any

from google.adk.models.lite_llm import LiteLlm

from strategy_agent.config import settings


def create_llm_model() -> Any:
    if not settings.adk_model.startswith("deepseek/"):
        return settings.adk_model

    return LiteLlm(
        model=settings.adk_model,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        api_base=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
        timeout=settings.llm_timeout_seconds,
    )
