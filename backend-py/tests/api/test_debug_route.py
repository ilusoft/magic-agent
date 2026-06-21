"""Tests for ``GET /api/agents/{agent_id}/runs/{conversation_id}/debug``.

Mirrors the .NET ``GetConversationDiagnosticsAsync`` action:
* 200 with the diagnostics payload (camelCase) when runs exist
* 404 when the diagnostics store has no runs for the conversation
* 400 when ``conversation_id`` is empty or whitespace
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.runs import router as runs_router
from src.application.agents.run_result import (
    AgentRunResult,
    AgentStepExecutionResult,
)
from src.application.runs.service import AgentRunsService
from src.infrastructure.diagnostics.store import (
    IAgentDiagnosticsStore,
    set_diagnostics_store,
)


class _InMemoryDiagnosticsStore(IAgentDiagnosticsStore):
    """Tiny in-memory diagnostics store for tests."""

    def __init__(self) -> None:
        self._runs: dict[str, list[AgentRunResult]] = {}

    async def save_run(
        self, conversation_id: str, run_result: AgentRunResult
    ) -> None:
        if not conversation_id:
            return
        self._runs.setdefault(conversation_id, []).append(run_result)

    async def get_runs(self, conversation_id: str) -> list[AgentRunResult]:
        return list(self._runs.get(conversation_id, []))


def _build_app(
    *,
    runs_by_conversation: dict[str, list[AgentRunResult]] | None = None,
) -> tuple[FastAPI, _InMemoryDiagnosticsStore]:
    app = FastAPI()
    app.include_router(runs_router)

    store = _InMemoryDiagnosticsStore()
    if runs_by_conversation:
        for cid, runs in runs_by_conversation.items():
            for run in runs:
                # Use a sync helper to populate, but the store is
                # async-only. Easiest is to just rely on save_run
                # being awaited via the running event loop later;
                # populate through ``_runs`` directly here.
                store._runs.setdefault(cid, []).append(run)  # noqa: SLF001
    set_diagnostics_store(store)

    # The service singleton is created lazily; supply a stub that
    # never gets called by the debug endpoint but is required to
    # avoid import-time errors.
    class _StubProvider:
        async def load_agent(self, _agent_id: str) -> dict | None:
            return None

    AgentRunsService(
        provider=_StubProvider(),  # type: ignore[arg-type]
        executor=type(  # type: ignore[arg-type]
            "_StubExecutor",
            (),
            {"execute_stream": staticmethod(lambda **_kw: None)},
        )(),
    )
    return app, store


def _sample_run(
    agent_id: str = "agent-1",
    status: str = "completed",
    conversation_id: str = "conv-1",
) -> AgentRunResult:
    step = AgentStepExecutionResult(
        name="chat",
        type="agent",
        output="Bonjour le monde",
        outcome="end",
        next_step=None,
        end_workflow=True,
        resolved_parameters={"message": "hello"},
    )
    return AgentRunResult(
        agent_id=agent_id,
        status=status,
        steps=[step],
        conversation_id=conversation_id,
        completed_at=datetime(2026, 1, 1, 12, 0, 0),
    )


class TestGetConversationDebug:
    """Pin the contract the SPA's ``loadDiagnostics`` call relies on."""

    def test_returns_runs_when_present(self) -> None:
        run = _sample_run()
        app, _store = _build_app(runs_by_conversation={"conv-1": [run]})
        client = TestClient(app)

        response = client.get("/agent-1/runs/conv-1/debug")

        assert response.status_code == 200
        body = response.json()
        assert body["conversationId"] == "conv-1"
        assert len(body["runs"]) == 1
        first = body["runs"][0]
        # camelCase payload, matching the SPA's ``AgentRunResult``.
        assert first["agentId"] == "agent-1"
        assert first["status"] == "completed"
        assert first["conversationId"] == "conv-1"
        assert first["completedAt"].startswith("2026-01-01T12:00:00")
        assert len(first["steps"]) == 1
        assert first["steps"][0]["name"] == "chat"
        assert first["steps"][0]["output"] == "Bonjour le monde"
        # ``resolvedParameters`` is camelCase, not ``resolved_parameters``.
        assert first["steps"][0]["resolvedParameters"] == {"message": "hello"}

    def test_returns_runs_in_chronological_order(self) -> None:
        runs = [
            _sample_run(status="completed", conversation_id="conv-1"),
            _sample_run(status="failed", conversation_id="conv-1"),
        ]
        app, _store = _build_app(runs_by_conversation={"conv-1": runs})
        client = TestClient(app)

        response = client.get("/agent-1/runs/conv-1/debug")

        assert response.status_code == 200
        body = response.json()
        assert [r["status"] for r in body["runs"]] == ["completed", "failed"]

    def test_returns_404_when_no_runs(self) -> None:
        app, _store = _build_app()
        client = TestClient(app)

        response = client.get("/agent-1/runs/missing/debug")

        assert response.status_code == 404

    def test_returns_400_when_conversation_id_is_empty(self) -> None:
        """FastAPI's path matching won't match a literal empty
        segment, but a whitespace-only ID should still be rejected.
        """
        app, _store = _build_app()
        client = TestClient(app)

        # ``%20`` decodes to a single space.
        response = client.get("/agent-1/runs/%20/debug")

        assert response.status_code == 400

    def test_agent_id_segment_does_not_filter_results(self) -> None:
        """The .NET controller puts ``agentId`` in the URL for
        routing but doesn't filter on it (conversations are
        globally unique). Mirror that behaviour.
        """
        run = _sample_run(agent_id="real-agent", conversation_id="conv-1")
        app, _store = _build_app(runs_by_conversation={"conv-1": [run]})
        client = TestClient(app)

        # Pass a different agent_id in the URL than what was
        # recorded on the run; the lookup is conversation-scoped.
        response = client.get("/some-other-agent/runs/conv-1/debug")

        assert response.status_code == 200
        body = response.json()
        assert body["runs"][0]["agentId"] == "real-agent"


class TestDiagnosticsStoreRoundTrip:
    """End-to-end: save a run, then read it back via the endpoint."""

    def test_run_saved_by_executor_is_visible_via_debug(self) -> None:
        from src.infrastructure.diagnostics.store import get_diagnostics_store

        store = _InMemoryDiagnosticsStore()
        set_diagnostics_store(store)

        run = _sample_run(conversation_id="round-trip")
        # Simulate what ``WorkflowExecutor.execute_stream`` does at
        # the end of a run.
        asyncio.run(store.save_run("round-trip", run))

        app = FastAPI()
        app.include_router(runs_router)
        client = TestClient(app)

        response = client.get("/agent-1/runs/round-trip/debug")
        assert response.status_code == 200
        body = response.json()
        assert body["conversationId"] == "round-trip"
        assert len(body["runs"]) == 1
        assert body["runs"][0]["agentId"] == "agent-1"
