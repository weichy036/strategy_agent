from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.agent_tool import (
    AgentTool,
    ForwardingArtifactService,
    _get_input_schema,
    _get_output_schema,
    validate_schema,
)
from google.adk.tools.tool_context import ToolContext
from google.adk.utils.context_utils import Aclosing
from google.genai import types

from strategy_agent.services.adk_event_adapter import extract_text_from_content
from strategy_agent.services.live_trace import emit_live_timeline_item
from strategy_agent.services.state_keys import AgentStateKeys


class TraceableAgentTool(AgentTool):
    """AgentTool that mirrors child-agent progress into parent ADK state."""

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        if self.skip_summarization:
            tool_context.actions.skip_summarization = True

        content = _build_child_input(self.agent, args)
        runner = _build_child_runner(self, tool_context)
        session = await _create_child_session(runner, tool_context)
        _trace_subagent(tool_context, self.agent.name, "subagent_start", "running", "开始分析")

        try:
            last_content, last_grounding_metadata = await _run_child_agent(
                runner=runner,
                session=session,
                content=content,
                tool_context=tool_context,
            )
        finally:
            await runner.close()

        _trace_subagent(tool_context, self.agent.name, "subagent_done", "success", "分析完成")
        if self.propagate_grounding_metadata and last_grounding_metadata:
            tool_context.state["temp:_adk_grounding_metadata"] = last_grounding_metadata
        return _child_result(self.agent, last_content)


def _build_child_input(agent: Any, args: dict[str, Any]) -> types.Content:
    input_schema = _get_input_schema(agent)
    if input_schema:
        input_value = input_schema.model_validate(args)
        text = input_value.model_dump_json(exclude_none=True)
    else:
        text = str(args.get("request") or "")
    return types.Content(role="user", parts=[types.Part.from_text(text=text)])


def _build_child_runner(tool: TraceableAgentTool, tool_context: ToolContext) -> Runner:
    invocation_context = tool_context._invocation_context
    app_name = invocation_context.app_name if invocation_context else tool.agent.name
    plugins = invocation_context.plugin_manager.plugins if tool.include_plugins and invocation_context else None
    return Runner(
        app_name=app_name,
        agent=tool.agent,
        artifact_service=ForwardingArtifactService(tool_context),
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
        credential_service=invocation_context.credential_service if invocation_context else None,
        plugins=plugins,
    )


async def _create_child_session(runner: Runner, tool_context: ToolContext):
    state = {key: value for key, value in tool_context.state.to_dict().items() if not key.startswith("_adk")}
    return await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=tool_context.user_id,
        state=state,
    )


async def _run_child_agent(
    *,
    runner: Runner,
    session: Any,
    content: types.Content,
    tool_context: ToolContext,
):
    last_content = None
    last_grounding_metadata = None
    async with Aclosing(runner.run_async(user_id=session.user_id, session_id=session.id, new_message=content)) as agen:
        async for event in agen:
            _mirror_child_event(tool_context, event)
            if event.actions.state_delta:
                tool_context.state.update(event.actions.state_delta)
            if event.content:
                last_content = event.content
                last_grounding_metadata = event.grounding_metadata
    return last_content, last_grounding_metadata


def _child_result(agent: Any, content: types.Content | None) -> Any:
    if content is None or content.parts is None:
        return ""
    merged_text = "\n".join(part.text for part in content.parts if part.text and not part.thought)
    output_schema = _get_output_schema(agent)
    return validate_schema(output_schema, merged_text) if output_schema else merged_text


def _mirror_child_event(tool_context: ToolContext, event: Any) -> None:
    author = str(getattr(event, "author", "") or "")
    for function_call in event.get_function_calls():
        name = str(function_call.name or "unknown_tool")
        _append_trace(
            tool_context,
            {
                "event_type": "subagent_tool_start",
                "actor": name,
                "status": "running",
                "stage": author or name,
                "message": f"{author or '子 Agent'} 调用 {name}",
            },
        )
    for function_response in event.get_function_responses():
        name = str(function_response.name or "unknown_tool")
        _append_trace(
            tool_context,
            {
                "event_type": "subagent_tool_done",
                "actor": name,
                "status": "done",
                "stage": author or name,
                "message": f"{author or '子 Agent'} 完成 {name}",
            },
        )

    text = extract_text_from_content(getattr(event, "content", None))
    if author and author != "user" and text and not event.get_function_calls() and not event.get_function_responses():
        _append_trace(
            tool_context,
            {
                "event_type": "subagent_message",
                "actor": author,
                "status": "done",
                "stage": author,
                "message": _short_text(text),
            },
        )


def _append_trace(tool_context: ToolContext, entry: dict[str, Any]) -> None:
    traced_entry = {"timestamp": datetime.now(timezone.utc).isoformat(), **entry}
    emit_live_timeline_item(traced_entry)
    current = tool_context.state.get(AgentStateKeys.TOOL_TRACE_BUFFER, [])
    if not isinstance(current, list):
        current = []
    tool_context.state[AgentStateKeys.TOOL_TRACE_BUFFER] = [*current, traced_entry]


def _trace_subagent(
    tool_context: ToolContext,
    agent_name: str,
    event_type: str,
    status: str,
    action: str,
) -> None:
    _append_trace(
        tool_context,
        {
            "event_type": event_type,
            "actor": agent_name,
            "status": status,
            "stage": agent_name,
            "message": f"{agent_name} {action}",
        },
    )


def _short_text(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}..."


__all__ = ["TraceableAgentTool"]
