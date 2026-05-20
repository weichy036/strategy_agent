from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ToolError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel, Generic[T]):
    ok: bool
    data: T | dict[str, Any] | None = None
    error: ToolError | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
