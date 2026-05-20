from __future__ import annotations

import json
from pathlib import Path

from strategy_agent.config import settings


def build_artifact_name(
    artifact_type: str,
    session_id: str,
    strategy_id: str | None = None,
    run_id: str | None = None,
    ext: str = "json",
) -> str:
    parts = [artifact_type, session_id]
    if strategy_id:
        parts.append(strategy_id)
    if run_id:
        parts.append(run_id)
    return "_".join(parts) + f".{ext}"


def persist_artifact_content(
    session_id: str,
    name: str,
    content: dict | list | str,
    content_type: str = "application/json",
) -> Path:
    artifact_dir = settings.artifact_root / session_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    target = artifact_dir / name

    if content_type == "text/markdown":
        target.write_text(str(content), encoding="utf-8")
    else:
        payload = content if isinstance(content, (dict, list)) else {"value": str(content)}
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
