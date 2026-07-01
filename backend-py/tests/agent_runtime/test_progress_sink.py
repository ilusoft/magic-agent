"""Tests for the SSE progress sink.

The sink is the wire-format contract that the Python backend shares
with the .NET backend. Any drift in event names or payload shape
breaks the SPA's ``AgentRunnerView`` SSE parser, so these tests
pin the format down.
"""

from __future__ import annotations

import json

import pytest

from src.agent_runtime.progress_sink import (
    AgentRunProgressSink,
    NoOpProgressSink,
    SseProgressSink,
)
from src.application.agents.run_result import (
    AgentIterationTrace,
    AgentRunResult,
    AgentStepExecutionResult,
    AgentToolCall,
)


class _CollectingSend:
    """ASGI-shaped send callable that records the bodies it receives."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, message: dict) -> None:
        self.messages.append(message)


def _parse_event(body: bytes) -> tuple[str, dict]:
    """Decode a single ``event: <name>\\ndata: <json>\\n\\n`` payload."""
    text = body.decode("utf-8")
    assert text.endswith("\n\n"), f"event missing trailing blank line: {text!r}"
    lines = text.rstrip("\n").split("\n")
    event_name: str | None = None
    data: str | None = None
    for line in lines:
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = line.split(":", 1)[1].strip()
    assert event_name is not None
    assert data is not None
    return event_name, json.loads(data)


class TestSseProgressSink:
    """Pin the wire format emitted to the SPA."""

    @pytest.fixture
    def send(self) -> _CollectingSend:
        return _CollectingSend()

    @pytest.fixture
    def sink(self, send: _CollectingSend) -> SseProgressSink:
        return SseProgressSink(send)

    @pytest.mark.asyncio
    async def test_step_start_event_format(
        self, sink: SseProgressSink, send: _CollectingSend
    ) -> None:
        await sink.step_start(
            agent_id="agent-1",
            step_name="translate",
            step_type="agent",
            iteration=2,
        )
        assert len(send.messages) == 1
        event_name, payload = _parse_event(send.messages[0]["body"])
        assert event_name == "step-start"
        assert payload == {
            "agentId": "agent-1",
            "stepName": "translate",
            "stepType": "agent",
            "iteration": 2,
        }

    @pytest.mark.asyncio
    async def test_step_complete_event_format(
        self, sink: SseProgressSink, send: _CollectingSend
    ) -> None:
        step = AgentStepExecutionResult(
            name="translate",
            type="agent",
            output="Bonjour le monde",
            outcome="next",
            next_step="summarize",
            end_workflow=False,
        )
        await sink.step_complete(
            agent_id="agent-1",
            step=step,
            elapsed_ms=1234.5,
        )
        event_name, payload = _parse_event(send.messages[0]["body"])
        assert event_name == "step-complete"
        assert payload["agentId"] == "agent-1"
        assert payload["elapsedMs"] == 1234.5
        assert payload["step"]["name"] == "translate"
        assert payload["step"]["output"] == "Bonjour le monde"
        assert payload["step"]["outcome"] == "next"
        assert payload["step"]["nextStep"] == "summarize"
        assert payload["step"]["endWorkflow"] is False

    @pytest.mark.asyncio
    async def test_run_complete_event_format(
        self, sink: SseProgressSink, send: _CollectingSend
    ) -> None:
        run_result = AgentRunResult(
            agent_id="agent-1",
            status="completed",
            steps=[
                AgentStepExecutionResult(
                    name="translate",
                    type="agent",
                    output="Bonjour le monde",
                )
            ],
            conversation_id="conv-1",
        )
        await sink.run_complete(run_result)
        event_name, payload = _parse_event(send.messages[0]["body"])
        assert event_name == "run-complete"
        assert payload["agentId"] == "agent-1"
        assert payload["status"] == "completed"
        assert payload["conversationId"] == "conv-1"
        assert payload["steps"][0]["name"] == "translate"

    @pytest.mark.asyncio
    async def test_messages_marked_as_more_body(
        self, sink: SseProgressSink, send: _CollectingSend
    ) -> None:
        await sink.step_start(
            agent_id="a", step_name="s", step_type="agent", iteration=0
        )
        assert send.messages[0]["more_body"] is True

    @pytest.mark.asyncio
    async def test_iteration_event_format(
        self, sink: SseProgressSink, send: _CollectingSend
    ) -> None:
        """Per-LLM-turn trace event surfaced in the SPA's trace panel."""
        trace = AgentIterationTrace(
            iteration=2,
            content="Let me check the docs first",
            tool_call_names=["docs_search"],
            has_tool_calls=True,
        )
        await sink.iteration(
            agent_id="agent-1", step_name="research", trace=trace
        )
        event_name, payload = _parse_event(send.messages[0]["body"])
        assert event_name == "agent-iteration"
        assert payload["agentId"] == "agent-1"
        assert payload["stepName"] == "research"
        assert payload["iteration"] == 2
        assert payload["content"] == "Let me check the docs first"
        assert payload["toolCallNames"] == ["docs_search"]
        assert payload["hasToolCalls"] is True
        # Timestamp must be a string so JSON.parse on the SPA side
        # can hydrate it into a Date without further coercion.
        assert isinstance(payload["timestamp"], str)

    @pytest.mark.asyncio
    async def test_tool_call_event_format(
        self, sink: SseProgressSink, send: _CollectingSend
    ) -> None:
        """Per-tool-execution trace event surfaced in the SPA's trace panel."""
        record = AgentToolCall(
            tool_name="docs_search",
            invocation_id="call_42",
            result='{"hits": 3}',
            arguments_json='{"query": "magic agent"}',
            error_message=None,
        )
        await sink.tool_call(
            agent_id="agent-1", step_name="research", tool_call=record
        )
        event_name, payload = _parse_event(send.messages[0]["body"])
        assert event_name == "tool-call"
        assert payload["agentId"] == "agent-1"
        assert payload["stepName"] == "research"
        assert payload["toolCall"]["toolName"] == "docs_search"
        assert payload["toolCall"]["invocationId"] == "call_42"
        assert payload["toolCall"]["result"] == '{"hits": 3}'
        assert payload["toolCall"]["argumentsJson"] == '{"query": "magic agent"}'


class TestNoOpProgressSink:
    """``NoOpProgressSink`` is the default for sync runs."""

    @pytest.mark.asyncio
    async def test_all_methods_are_noops(self) -> None:
        sink = NoOpProgressSink()
        # Methods should return ``None`` and accept any keyword args.
        assert await sink.step_start(agent_id="a", step_name="s", step_type="t", iteration=0) is None
        assert (
            await sink.step_complete(
                agent_id="a",
                step=AgentStepExecutionResult(
                    name="s", type="t", output="o"
                ),
                elapsed_ms=1.0,
            )
            is None
        )
        assert (
            await sink.run_complete(
                AgentRunResult(agent_id="a", status="completed")
            )
            is None
        )
        assert (
            await sink.iteration(
                agent_id="a",
                step_name="s",
                trace=AgentIterationTrace(iteration=0, content="hi"),
            )
            is None
        )
        assert (
            await sink.tool_call(
                agent_id="a",
                step_name="s",
                tool_call=AgentToolCall(tool_name="t"),
            )
            is None
        )


class TestProtocolShape:
    """``SseProgressSink`` and ``NoOpProgressSink`` should both be
    usable where the protocol is expected."""

    def test_sse_sink_satisfies_protocol(self) -> None:
        sink: AgentRunProgressSink = SseProgressSink(_CollectingSend())
        assert hasattr(sink, "step_start")
        assert hasattr(sink, "step_complete")
        assert hasattr(sink, "run_complete")
        assert hasattr(sink, "iteration")
        assert hasattr(sink, "tool_call")

    def test_noop_sink_satisfies_protocol(self) -> None:
        sink: AgentRunProgressSink = NoOpProgressSink()
        assert hasattr(sink, "step_start")
        assert hasattr(sink, "step_complete")
        assert hasattr(sink, "run_complete")
        assert hasattr(sink, "iteration")
        assert hasattr(sink, "tool_call")
