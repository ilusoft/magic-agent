"""Progress sink abstractions and the SSE implementation.

The .NET backend exposes a small ``IAgentRunProgressSink`` interface
that emits three kinds of events while a workflow is running:

* ``step-start``     – just before a step is executed
* ``step-complete``  – just after a step finished
* ``run-complete``   – after the run's final output is known
* ``agent-iteration``– per LLM turn inside an agent step (assistant
                       text + tool calls requested on that turn)
* ``tool-call``      – per tool execution performed by an agent

The frontend SPA is wired to that exact event naming and the
camelCase payload fields, so the Python backend has to mirror it
byte-for-byte for the same UI code to work against both stacks.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import structlog

from src.application.agents.run_result import (
    AgentIterationTrace,
    AgentRunResult,
    AgentStepExecutionResult,
    AgentToolCall,
)

logger = structlog.get_logger(__name__)


class AgentRunProgressSink(Protocol):
    """Minimal progress sink surface used by ``WorkflowExecutor``.

    Implementations only need to handle the happy path; errors
    inside the workflow are surfaced through ``step_complete``
    (with an ``error`` annotation) or by raising from the
    executor itself.
    """

    async def step_start(
        self,
        agent_id: str,
        step_name: str,
        step_type: str,
        iteration: int,
    ) -> None: ...

    async def step_complete(
        self,
        agent_id: str,
        step: AgentStepExecutionResult,
        elapsed_ms: float,
    ) -> None: ...

    async def run_complete(self, run_result: AgentRunResult) -> None: ...

    async def iteration(
        self,
        agent_id: str,
        step_name: str,
        trace: AgentIterationTrace,
    ) -> None: ...

    async def tool_call(
        self,
        agent_id: str,
        step_name: str,
        tool_call: AgentToolCall,
    ) -> None: ...


class NoOpProgressSink:
    """Default sink used by the non-streaming ``/runs`` path.

    Implements the protocol so callers can pass it unconditionally;
    every method is a no-op.
    """

    async def step_start(
        self,
        agent_id: str,
        step_name: str,
        step_type: str,
        iteration: int,
    ) -> None:
        return None

    async def step_complete(
        self,
        agent_id: str,
        step: AgentStepExecutionResult,
        elapsed_ms: float,
    ) -> None:
        return None

    async def run_complete(self, run_result: AgentRunResult) -> None:
        return None

    async def iteration(
        self,
        agent_id: str,
        step_name: str,
        trace: AgentIterationTrace,
    ) -> None:
        return None

    async def tool_call(
        self,
        agent_id: str,
        step_name: str,
        tool_call: AgentToolCall,
    ) -> None:
        return None


class SseProgressSink:
    """Writes ``text/event-stream`` payloads to an ASGI response.

    Mirrors ``MagicAgent.Api/Application/AgentRunner/StreamingAgentRunProgressSink.cs``
    line-for-line: each event is serialised as

        event: <name>\\n
        data: <json>\\n
        \\n

    using kebab-case event names (``step-start``, ``step-complete``,
    ``run-complete``) and camelCase payload fields (``agentId``,
    ``stepName``, ``stepType``, ``iteration``, ``step``,
    ``elapsedMs``, ``conversationId``).
    """

    def __init__(self, send: Any) -> None:
        self._send = send

    async def _write(self, event_name: str, payload: dict[str, Any]) -> None:
        body = f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
        await self._send(
            {
                "type": "http.response.body",
                "body": body.encode("utf-8"),
                "more_body": True,
            }
        )

    async def step_start(
        self,
        agent_id: str,
        step_name: str,
        step_type: str,
        iteration: int,
    ) -> None:
        await self._write(
            "step-start",
            {
                "agentId": agent_id,
                "stepName": step_name,
                "stepType": step_type,
                "iteration": iteration,
            },
        )

    async def step_complete(
        self,
        agent_id: str,
        step: AgentStepExecutionResult,
        elapsed_ms: float,
    ) -> None:
        await self._write(
            "step-complete",
            {
                "agentId": agent_id,
                "step": step.to_dict(),
                "elapsedMs": elapsed_ms,
            },
        )

    async def run_complete(self, run_result: AgentRunResult) -> None:
        await self._write("run-complete", run_result.to_dict())

    async def iteration(
        self,
        agent_id: str,
        step_name: str,
        trace: AgentIterationTrace,
    ) -> None:
        await self._write(
            "agent-iteration",
            {
                "agentId": agent_id,
                "stepName": step_name,
                "iteration": trace.iteration,
                "content": trace.content,
                "toolCallNames": trace.tool_call_names,
                "hasToolCalls": trace.has_tool_calls,
                "timestamp": trace.timestamp,
            },
        )

    async def tool_call(
        self,
        agent_id: str,
        step_name: str,
        tool_call: AgentToolCall,
    ) -> None:
        await self._write(
            "tool-call",
            {
                "agentId": agent_id,
                "stepName": step_name,
                "toolCall": tool_call.to_dict(),
            },
        )
