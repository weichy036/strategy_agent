from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from strategy_agent.config import settings


def supports_native_output_schema() -> bool:
    return not settings.adk_model.startswith("deepseek/")


def output_schema_kwargs(schema: type[BaseModel]) -> dict[str, Any]:
    if supports_native_output_schema():
        return {"output_schema": schema}
    return {}


def json_contract_instruction(schema: type[BaseModel]) -> str:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    return (
        "只返回一个符合下面 schema 的 JSON 对象。"
        "不要使用 Markdown 代码块，不要输出解释文字。"
        f"JSON schema: {schema_json}"
    )
