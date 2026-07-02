"""Reproduces the camelCase field-name mismatch between the SPA and the
``RunRequest`` schema. The SPA sends ``conversationId`` (camelCase) but
the schema field is named ``conversation_id`` (snake_case) without an
alias, so Pydantic v2 silently drops the value and every round is
treated as a brand-new conversation.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.runs import router as runs_router
from src.application.agents.run_result import (
    AgentRunResult,
    AgentStepExecutionResult,
)
from src.application.runs.service import AgentRunsService


class _FakeProvider:
    def __init__(self, agents: dict[str, dict]) -> None:
        self._agents = agents

    async def load_agent(self, agent_id: str) -> dict | None:
        return self._agents.get(agent_id)

    async def get_full_document(self) -> dict:
        return {"agents": list(self._agents.values())}


class _FakeExecutor:
    def __init__(self) -> None:
        self.last_conversation_id: str | None = None

    async def execute_stream(
        self,
        agent_definition: dict,
        input_text: str,
        parameters: dict | None = None,
        progress_sink=None,
        conversation_id: str | None = None,
        document: dict | None = None,
    ) -> AgentRunResult:
        self.last_conversation_id = conversation_id
        step = AgentStepExecutionResult(
            name="chat",
            type="agent",
            output="ok",
            end_workflow=True,
        )
        return AgentRunResult(
            agent_id="agent-x",
            status="completed",
            steps=[step],
            conversation_id=conversation_id or "fresh-uuid",
        )


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(runs_router)
    agent_def = {
        "id": "agent-x",
        "name": "agent-x",
        "defaultParameters": {},
        "streaming": {"enabled": False},
        "steps": [],
    }
    service = AgentRunsService(
        provider=_FakeProvider({"agent-x": agent_def}),
        executor=_FakeExecutor(),  # type: ignore[arg-type]
    )
    import src.application.runs.service as service_module
    service_module._runs_service = service  # noqa: SLF001
    return TestClient(app)


def test_camelcase_conversation_id_is_accepted(client: TestClient) -> None:
    """The SPA sends ``conversationId`` (camelCase). The schema must
    accept that field name and forward it to the executor so the
    conversation context can be reused across rounds.
    """
    response = client.post(
        "/agent-x/runs",
        json={"input": "hi", "conversationId": "round-2", "parameters": {}},
    )
    assert response.status_code == 200, response.text
    import src.application.runs.service as service_module

    assert service_module._runs_service is not None  # noqa: SLF001
    assert service_module._runs_service._executor.last_conversation_id == "round-2"  # noqa: SLF001


def test_snakecase_conversation_id_still_works(client: TestClient) -> None:
    """The snake_case field name is kept as an alias for backward
    compatibility with the .NET backend and any internal callers
    that haven't migrated to camelCase yet.
    """
    response = client.post(
        "/agent-x/runs",
        json={"input": "hi", "conversation_id": "round-3", "parameters": {}},
    )
    assert response.status_code == 200, response.text
    import src.application.runs.service as service_module

    assert service_module._runs_service is not None  # noqa: SLF001
    assert service_module._runs_service._executor.last_conversation_id == "round-3"  # noqa: SLF001
