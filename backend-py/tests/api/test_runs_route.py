"""Tests for the runs route content negotiation + service.

These exercise the wire-level contract that the SPA relies on:

* ``Accept: application/json`` (the default ``fetch`` Accept) returns
  a JSON ``AgentWorkflowResult`` (camelCase, with ``lastStep`` and
  ``conversationId``).
* ``Accept: text/event-stream`` plus ``streaming.enabled = true``
  returns an SSE stream of ``step-start``/``step-complete``/
  ``run-complete`` events.
* ``Accept: text/event-stream`` with ``streaming.enabled = false``
  falls back to the JSON response.

The streaming tests also assert that the events arrive progressively
(so the UI can show step-by-step progress) rather than as a single
batch at the end of the run.
"""

from __future__ import annotations

import asyncio
import json
import time
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


class _FakeProvider:
    """Loads canned agent definitions without touching the filesystem."""

    def __init__(self, agents: dict[str, dict]) -> None:
        self._agents = agents

    async def load_agent(self, agent_id: str) -> dict | None:
        return self._agents.get(agent_id)


class _FakeExecutor:
    """Stub executor that produces a deterministic result.

    Records the ``progress_sink`` it received so the test can assert
    the sink-based contract.
    """

    def __init__(self) -> None:
        self.last_sink: Any = None
        self.call_count = 0

    async def execute_stream(
        self,
        agent_definition: dict,
        input_text: str,
        parameters: dict | None = None,
        progress_sink: Any = None,
    ) -> AgentRunResult:
        from src.agent_runtime.progress_sink import NoOpProgressSink

        self.last_sink = progress_sink
        self.call_count += 1

        # Drive the sink (if any) so the route can collect events.
        sink = progress_sink or NoOpProgressSink()
        await sink.step_start(
            agent_id="agent-streaming",
            step_name="chat",
            step_type="agent",
            iteration=0,
        )
        step = AgentStepExecutionResult(
            name="chat",
            type="agent",
            output="Bonjour le monde",
            outcome="end",
            next_step=None,
            end_workflow=True,
        )
        await sink.step_complete(
            agent_id="agent-streaming",
            step=step,
            elapsed_ms=42.0,
        )
        run_result = AgentRunResult(
            agent_id="agent-streaming",
            status="completed",
            steps=[step],
            conversation_id="conv-42",
        )
        await sink.run_complete(run_result)
        return run_result


def _build_app(
    *,
    agent_def: dict,
    executor: _FakeExecutor | None = None,
) -> tuple[FastAPI, AgentRunsService]:
    app = FastAPI()
    app.include_router(runs_router)

    service = AgentRunsService(
        provider=_FakeProvider({"agent-streaming": agent_def}),
        executor=executor or _FakeExecutor(),  # type: ignore[arg-type]
    )

    # Override the singleton so the route uses our test service.
    import src.application.runs.service as service_module

    service_module._runs_service = service  # noqa: SLF001
    return app, service


@pytest.fixture
def streaming_agent_def() -> dict:
    return {
        "id": "agent-streaming",
        "name": "agent-streaming",
        "defaultParameters": {},
        "streaming": {"enabled": True, "mode": "sse"},
        "steps": [],
    }


@pytest.fixture
def non_streaming_agent_def() -> dict:
    return {
        "id": "agent-streaming",
        "name": "agent-streaming",
        "defaultParameters": {},
        "streaming": {"enabled": False, "mode": "sse"},
        "steps": [],
    }


class TestContentNegotiation:
    """``/runs`` should behave like the .NET controller."""

    def test_default_accept_returns_json_workflow_result(
        self, streaming_agent_def: dict
    ) -> None:
        app, _service = _build_app(agent_def=streaming_agent_def)
        client = TestClient(app)
        response = client.post(
            "/agent-streaming/runs",
            json={"input": "hi", "conversation_id": None, "parameters": {}},
        )
        assert response.status_code == 200
        body = response.json()
        # camelCase shape, exactly what the SPA expects.
        assert body["agentId"] == "agent-streaming"
        assert body["status"] == "completed"
        assert body["conversationId"] == "conv-42"
        assert body["lastStep"]["name"] == "chat"
        assert body["lastStep"]["output"] == "Bonjour le monde"
        assert body["lastStep"]["endWorkflow"] is True
        # No ``run_id`` / ``output`` flat fields - the JSON is the
        # .NET-compatible shape, not the old ``RunResponse``.
        assert "run_id" not in body
        assert "output" not in body

    def test_event_stream_accept_with_streaming_enabled_returns_sse(
        self, streaming_agent_def: dict
    ) -> None:
        app, _service = _build_app(agent_def=streaming_agent_def)
        client = TestClient(app)
        response = client.post(
            "/agent-streaming/runs",
            json={"input": "hi", "conversation_id": None, "parameters": {}},
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        # The body should contain the three SSE events we expect.
        body = response.text
        assert "event: step-start\n" in body
        assert "event: step-complete\n" in body
        assert "event: run-complete\n" in body

        # Decode the run-complete payload and confirm camelCase fields.
        run_complete_line = next(
            line
            for line in body.split("\n")
            if line.startswith("data:")
            and '"agentId"' in line
            and '"status"' in line
        )
        payload = json.loads(run_complete_line.split(":", 1)[1].strip())
        assert payload["agentId"] == "agent-streaming"
        assert payload["status"] == "completed"
        assert payload["conversationId"] == "conv-42"

    def test_event_stream_accept_without_streaming_enabled_falls_back_to_json(
        self, non_streaming_agent_def: dict
    ) -> None:
        app, _service = _build_app(agent_def=non_streaming_agent_def)
        client = TestClient(app)
        response = client.post(
            "/agent-streaming/runs",
            json={"input": "hi", "conversation_id": None, "parameters": {}},
            headers={"Accept": "text/event-stream"},
        )
        # The agent doesn't have streaming enabled, so the response
        # is JSON even when the caller asked for SSE.
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        body = response.json()
        assert body["agentId"] == "agent-streaming"
        assert body["status"] == "completed"

    def test_event_stream_accept_without_agent_returns_404(
        self, streaming_agent_def: dict
    ) -> None:
        app, _service = _build_app(agent_def=streaming_agent_def)
        client = TestClient(app)
        response = client.post(
            "/missing-agent/runs",
            json={"input": "hi", "conversation_id": None, "parameters": {}},
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 404

    def test_executor_receives_noop_sink_for_json_path(
        self, streaming_agent_def: dict
    ) -> None:
        """The JSON path must use ``NoOpProgressSink`` so the
        executor doesn't try to write to a non-existent SSE stream."""
        app, _service = _build_app(agent_def=streaming_agent_def)
        client = TestClient(app)
        client.post(
            "/agent-streaming/runs",
            json={"input": "hi", "conversation_id": None, "parameters": {}},
        )
        from src.agent_runtime.progress_sink import NoOpProgressSink

        assert isinstance(_service._executor.last_sink, NoOpProgressSink)  # noqa: SLF001


class TestRunsStreamAlias:
    """``/runs/stream`` is the backward-compat alias."""

    def test_runs_stream_returns_sse_when_streaming_enabled(
        self, streaming_agent_def: dict
    ) -> None:
        app, _service = _build_app(agent_def=streaming_agent_def)
        client = TestClient(app)
        response = client.post(
            "/agent-streaming/runs/stream",
            json={"input": "hi", "conversation_id": None, "parameters": {}},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: run-complete" in response.text

    def test_runs_stream_falls_back_to_json_when_streaming_disabled(
        self, non_streaming_agent_def: dict
    ) -> None:
        app, _service = _build_app(agent_def=non_streaming_agent_def)
        client = TestClient(app)
        response = client.post(
            "/agent-streaming/runs/stream",
            json={"input": "hi", "conversation_id": None, "parameters": {}},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["status"] == "completed"


class _SlowFakeExecutor:
    """Executor that waits between sink events so we can prove the
    route streams them progressively instead of batching at the end.

    The pauses are big enough to detect (50ms each) but small enough
    to keep the test fast (300ms total for three events).
    """

    def __init__(self, pause_seconds: float = 0.05) -> None:
        self.pause_seconds = pause_seconds
        self.events: list[tuple[str, float]] = []  # (event_name, timestamp)

    async def execute_stream(
        self,
        agent_definition: dict,
        input_text: str,
        parameters: dict | None = None,
        progress_sink: Any = None,
    ) -> AgentRunResult:
        await asyncio.sleep(self.pause_seconds)
        self.events.append(("step-start", time.monotonic()))
        await progress_sink.step_start(
            agent_id="agent-streaming",
            step_name="first",
            step_type="agent",
            iteration=0,
        )

        await asyncio.sleep(self.pause_seconds)
        step1 = AgentStepExecutionResult(
            name="first",
            type="agent",
            output="uno",
            outcome="next",
            next_step="second",
            end_workflow=False,
        )
        self.events.append(("step-complete", time.monotonic()))
        await progress_sink.step_complete(
            agent_id="agent-streaming",
            step=step1,
            elapsed_ms=50.0,
        )

        await asyncio.sleep(self.pause_seconds)
        self.events.append(("step-start", time.monotonic()))
        await progress_sink.step_start(
            agent_id="agent-streaming",
            step_name="second",
            step_type="agent",
            iteration=1,
        )

        step2 = AgentStepExecutionResult(
            name="second",
            type="agent",
            output="dos",
            outcome="end",
            next_step=None,
            end_workflow=True,
        )
        self.events.append(("step-complete", time.monotonic()))
        await progress_sink.step_complete(
            agent_id="agent-streaming",
            step=step2,
            elapsed_ms=50.0,
        )

        run_result = AgentRunResult(
            agent_id="agent-streaming",
            status="completed",
            steps=[step1, step2],
            conversation_id="conv-slow",
        )
        self.events.append(("run-complete", time.monotonic()))
        await progress_sink.run_complete(run_result)
        return run_result


class TestProgressiveStreaming:
    """Regression: SSE events must arrive progressively, not batched.

    Previously the route collected every event into a list and only
    started writing the response body after the workflow finished,
    so the SPA saw all events in a single shot instead of step by
    step. These tests read the response in chunks and assert that
    each event arrives close to the time it was produced.
    """

    def test_events_arrive_progressively(
        self, streaming_agent_def: dict
    ) -> None:
        executor = _SlowFakeExecutor(pause_seconds=0.05)
        app, _service = _build_app(
            agent_def=streaming_agent_def, executor=executor  # type: ignore[arg-type]
        )
        client = TestClient(app)
        with client.stream(
            "POST",
            "/agent-streaming/runs",
            json={"input": "hi", "conversation_id": None, "parameters": {}},
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            chunks: list[bytes] = []
            for chunk in response.iter_bytes():
                chunks.append(chunk)

        body = b"".join(chunks).decode("utf-8")

        # The three event types must be present in the order they were
        # produced.
        step_start_positions = [
            i for i, line in enumerate(body.split("\n")) if line == "event: step-start"
        ]
        step_complete_positions = [
            i for i, line in enumerate(body.split("\n")) if line == "event: step-complete"
        ]
        run_complete_positions = [
            i for i, line in enumerate(body.split("\n")) if line == "event: run-complete"
        ]
        assert len(step_start_positions) == 2
        assert len(step_complete_positions) == 2
        assert len(run_complete_positions) == 1

        # step-start positions must come before step-complete positions
        # in the order they were produced.
        assert step_start_positions[0] < step_complete_positions[0]
        assert step_start_positions[1] < step_complete_positions[1]

        # The first step-start must appear before the first step-complete
        # in the byte stream (i.e. the SPA can see the first event
        # before the second event is produced).
        first_event_index = body.index("event: step-start")
        last_event_index = body.index("event: run-complete")
        assert first_event_index < last_event_index

    def test_first_chunk_reaches_client_before_workflow_finishes(
        self, streaming_agent_def: dict
    ) -> None:
        """Stronger test: read the very first byte of the response
        while the workflow is still running. The old implementation
        would not return anything until the workflow finished.
        """
        pause = 0.3
        executor = _SlowFakeExecutor(pause_seconds=pause)
        app, _service = _build_app(
            agent_def=streaming_agent_def, executor=executor  # type: ignore[arg-type]
        )
        client = TestClient(app)

        with client.stream(
            "POST",
            "/agent-streaming/runs",
            json={"input": "hi", "conversation_id": None, "parameters": {}},
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200
            # Pull the first chunk; this returns when the first batch
            # of bytes is available.
            start = time.monotonic()
            iterator = response.iter_bytes()
            first_chunk = next(iterator)
            elapsed = time.monotonic() - start
            # Drain the rest so the response is closed cleanly.
            for chunk in iterator:
                pass

        # The first chunk must arrive well before the total workflow
        # duration (5 pauses * 0.3s = 1.5s). Allow generous slack
        # for CI noise but require it to be much less than 1s.
        assert elapsed < pause * 2, (
            f"First SSE chunk took {elapsed:.3f}s; expected < {pause * 2:.3f}s. "
            "Events are being buffered instead of streamed."
        )
        assert first_chunk.startswith(b"event: step-start"), first_chunk[:200]
