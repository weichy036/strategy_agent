from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


def apply_conversation_revision(schema: dict[str, Any] | None, conversation_context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Apply the structured revision context to a Strategy Schema draft.

    LLM agents are good at understanding "change the previous strategy to ...",
    but the executable schema should be patched deterministically before tools run.
    """

    if not isinstance(schema, dict):
        return schema
    context = conversation_context if isinstance(conversation_context, dict) else {}
    if context.get("turn_type") != "strategy_revision" and not context.get("patch_hints"):
        return schema

    out = deepcopy(schema)
    for raw_path, value in _normalized_patch_hints(context.get("patch_hints")).items():
        _set_path(out, raw_path.split("."), value)

    _apply_semantic_ranking_patch(out, context)
    _refresh_revision_metadata(out, context)
    return out


def _normalized_patch_hints(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    aliases = {
        "selection.ranking.direction": "selection.ranking.order",
        "ranking.direction": "selection.ranking.order",
        "ranking.order": "selection.ranking.order",
        "ranking.top_n": "selection.ranking.top_n",
        "position_count": "portfolio.position_count",
    }
    allowed_prefixes = (
        "selection.",
        "portfolio.",
        "universe.",
        "period.",
        "execution.",
        "costs.",
        "constraints.",
        "metadata.",
    )
    patch: dict[str, Any] = {}
    for path, patch_value in value.items():
        normalized = aliases.get(str(path), str(path))
        if normalized == "selection.ranking.order":
            patch_value = _normalize_order(patch_value)
        if not normalized.startswith(allowed_prefixes):
            continue
        patch[normalized] = patch_value
    return patch


def _apply_semantic_ranking_patch(schema: dict[str, Any], context: dict[str, Any]) -> None:
    text = " ".join(
        str(context.get(key) or "")
        for key in ("rewritten_query", "revision_summary", "last_user_query", "rationale")
    )
    if not text:
        return

    ranking = ((schema.get("selection") or {}).get("ranking") or {})
    sort_by = str(ranking.get("sort_by") or "")
    talks_about_market_cap = "市值" in text or sort_by in {"total_mv", "circ_mv", "market_cap"}
    if talks_about_market_cap and any(token in text for token in ("最小", "小市值", "升序", "asc")):
        _set_path(schema, ["selection", "ranking", "order"], "asc")
    elif talks_about_market_cap and any(token in text for token in ("最大", "大市值", "降序", "desc")):
        _set_path(schema, ["selection", "ranking", "order"], "desc")

    top_n = _extract_top_n(text)
    if top_n:
        _set_path(schema, ["selection", "ranking", "top_n"], top_n)
        _set_path(schema, ["portfolio", "position_count"], top_n)


def _refresh_revision_metadata(schema: dict[str, Any], context: dict[str, Any]) -> None:
    rewritten = context.get("rewritten_query")
    if rewritten:
        _set_path(schema, ["metadata", "source_query"], rewritten)

    if schema.get("strategy_type") != "cross_sectional_rotation":
        return
    refreshed_name = _rotation_name(schema)
    if refreshed_name:
        schema["name"] = refreshed_name
        schema["strategy_id"] = refreshed_name


def _rotation_name(schema: dict[str, Any]) -> str | None:
    selection = schema.get("selection") or {}
    ranking = selection.get("ranking") or {}
    sort_by = str(ranking.get("sort_by") or "")
    order = str(ranking.get("order") or "desc")
    top_n = ranking.get("top_n") or (schema.get("portfolio") or {}).get("position_count")
    if not top_n:
        return None
    if sort_by in {"total_mv", "market_cap"}:
        direction = "最小" if order == "asc" else "最大"
        return f"每月买入上月市值{direction}的{top_n}只股票"
    if sort_by == "circ_mv":
        direction = "最小" if order == "asc" else "最大"
        return f"每月买入上月流通市值{direction}的{top_n}只股票"
    return None


def _extract_top_n(text: str) -> int | None:
    match = re.search(r"(\d+)\s*只", text)
    if not match:
        return None
    try:
        value = int(match.group(1))
    except ValueError:
        return None
    return value if value > 0 else None


def _normalize_order(value: Any) -> Any:
    text = str(value).lower()
    if text in {"asc", "ascending", "升序", "最小", "小"}:
        return "asc"
    if text in {"desc", "descending", "降序", "最大", "大"}:
        return "desc"
    return value


def _set_path(target: dict[str, Any], parts: list[str], value: Any) -> None:
    if not parts:
        return
    node = target
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


__all__ = ["apply_conversation_revision"]
