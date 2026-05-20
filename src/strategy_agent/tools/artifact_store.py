from __future__ import annotations

from strategy_agent.schemas.tool_contracts import ToolError, ToolResponse
from strategy_agent.services.artifact_manager import build_artifact_name, persist_artifact_content


def store_artifact(
    artifact_type: str,
    session_id: str,
    content: dict | list | str,
    strategy_id: str | None = None,
    run_id: str | None = None,
    content_type: str = "application/json",
) -> ToolResponse[dict]:
    if not session_id:
        return ToolResponse(
            ok=False,
            error=ToolError(code="artifact_store_failed", message="缺少 session_id"),
        )
    ext = "md" if content_type == "text/markdown" else "json"
    name = build_artifact_name(artifact_type, session_id, strategy_id=strategy_id, run_id=run_id, ext=ext)
    uri = f"artifact://{session_id}/{name}"
    try:
        file_path = persist_artifact_content(
            session_id=session_id,
            name=name,
            content=content,
            content_type=content_type,
        )
    except Exception as exc:  # noqa: BLE001
        return ToolResponse(
            ok=False,
            error=ToolError(
                code="artifact_store_failed",
                message="Artifact 落盘失败",
                details={"reason": str(exc), "name": name, "session_id": session_id},
            ),
        )
    return ToolResponse(
        ok=True,
        data={
            "artifact_id": name,
            "artifact_type": artifact_type,
            "name": name,
            "uri": uri,
            "file_path": str(file_path),
            "preview": content if isinstance(content, str) else None,
        },
        meta={"content_type": content_type},
    )
