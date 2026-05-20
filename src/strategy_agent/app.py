from __future__ import annotations

from google.adk import Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService

from strategy_agent.agents import create_research_orchestrator_agent
from strategy_agent.config import settings


def build_runner() -> Runner:
    root_agent = create_research_orchestrator_agent()
    return Runner(
        app_name=settings.project_name,
        agent=root_agent,
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
        memory_service=InMemoryMemoryService(),
        auto_create_session=True,
    )


def main() -> None:
    runner = build_runner()
    agent_name = getattr(runner.agent, "name", "unknown")
    print(f"{settings.project_name} scaffold is ready.")
    print(f"Root agent: {agent_name}")
    print("Current stage: ADK runner, parser/validation/clarification loop, and backtest flows are wired.")
    print("Next step: integrate API/UI, persist session state, and improve metrics/reporting depth.")
