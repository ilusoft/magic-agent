"""Agent run execution endpoints.

The ``/api/agents/{agent_id}/runs`` endpoint mirrors the .NET
backend's ``AgentRunsController``:

* If the request's ``Accept`` header includes ``text/event-stream``
  **and** the agent definition has ``streaming.enabled = true``,
  the response is an SSE stream of ``step-start`` / ``step-complete``
  / ``run-complete`` events (camelCase payload, kebab-case event
  names).
* Otherwise the response is a JSON ``AgentWorkflowResult`` (the
  same shape the .NET backend returns for non-streaming runs).

The ``/api/agents/{agent_id}/runs/stream`` route is kept as a
backward-compat alias for clients that opt into streaming via the
URL instead of content negotiation.

The ``GET /api/agents/{agent_id}/runs/{conversation_id}/debug``
endpoint mirrors the .NET ``GetConversationDiagnosticsAsync``
action: it returns the full history of runs for a conversation so
the SPA can render the workflow execution panel.

Streaming implementation note
-----------------------------
The SSE stream is delivered progressively: the route runs the
workflow in a background task and bridges the progress sink to the
HTTP response body via an ``asyncio.Queue``. Each event the sink
emits is queued, then yielded by the ``StreamingResponse`` generator
as soon as it arrives, so the SPA sees step-by-step progress rather
than a single batch at the end of the run.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse

from src.application.runs.schemas import (
    AgentConversationDiagnostics,
    RunRequest,
)
from src.application.runs.service import get_runs_service
from src.application.agents.exceptions import AgentNotFoundError
from src.infrastructure.diagnostics.store import get_diagnostics_store

logger = structlog.get_logger(__name__)

router = APIRouter()


def _accepts_event_stream(request: Request) -> bool:
    """Return True if any of the request's ``Accept`` values contains
    ``text/event-stream``.

    Mirrors the helper in
    ``backend/src/MagicAgent.Api/Controllers/AgentRunsController.cs``.
    """
    accept_header = request.headers.get("accept")
    if not accept_header:
        return False
    return any(
        "text/event-stream" in value.lower()
        for value in accept_header.split(",")
    )


async def _should_stream(agent_id: str, request: Request) -> bool:
    """Decide whether to stream the response.

    The .NET controller only streams when both conditions hold:
    the caller opted in via ``Accept`` **and** the agent definition
    explicitly enables streaming.
    """
    if not _accepts_event_stream(request):
        return False

    provider = get_runs_service()._provider  # noqa: SLF001 (internal access)
    agent_def = await provider.load_agent(agent_id)
    if agent_def is None:
        raise AgentNotFoundError(agent_id)

    streaming = agent_def.get("streaming") or {}
    return bool(streaming.get("enabled"))


@router.post("/{agent_id}/runs")
async def trigger_agent_run(
    agent_id: str,
    request_body: RunRequest,
    request: Request,
) -> Response:
    """Trigger an agent run.

    Mirrors the .NET controller's content-negotiated behaviour:
    streams SSE when ``Accept: text/event-stream`` is set and the
    agent is configured for streaming, otherwise returns a JSON
    ``AgentWorkflowResult``.
    """
    service = get_runs_service()

    try:
        if await _should_stream(agent_id, request):
            return await _build_sse_response(agent_id, request_body, service)

        return await _build_json_response(agent_id, request_body, service)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{agent_id}/runs/stream")
async def stream_agent_run(
    agent_id: str,
    request_body: RunRequest,
) -> Response:
    """Backward-compat streaming alias.

    Always streams when the agent has ``streaming.enabled = true``;
    falls back to JSON when streaming is disabled. Clients are
    encouraged to use ``POST /runs`` with ``Accept: text/event-stream``
    instead so the URL is identical between streaming and
    non-streaming workflows.
    """
    service = get_runs_service()

    try:
        provider = service._provider  # noqa: SLF001
        agent_def = await provider.load_agent(agent_id)
        if agent_def is None:
            raise AgentNotFoundError(agent_id)
        streaming = agent_def.get("streaming") or {}
        if not streaming.get("enabled"):
            return await _build_json_response(agent_id, request_body, service)
        return await _build_sse_response(agent_id, request_body, service)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/{agent_id}/runs/{conversation_id}/debug")
async def get_conversation_debug(
    agent_id: str,
    conversation_id: str,
) -> Response:
    """Return the full run history for a conversation.

    Mirrors the .NET ``GetConversationDiagnosticsAsync`` action:
    * 400 when ``conversation_id`` is empty/whitespace
    * 404 when the diagnostics store has no runs for the
      conversation
    * 200 with ``{ conversationId, runs: [...] }`` otherwise

    The ``agent_id`` segment is part of the URL for parity with
    the .NET controller but isn't used to filter the lookup —
    conversation IDs are globally unique, just like the .NET
    ``InMemoryAgentDiagnosticsStore`` keys them.
    """
    if not conversation_id or not conversation_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="conversation_id is required",
        )

    diagnostics_store = get_diagnostics_store()
    runs = await diagnostics_store.get_runs(conversation_id)

    if not runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No diagnostics available for conversation '{conversation_id}'.",
        )

    diagnostics = AgentConversationDiagnostics(
        conversation_id=conversation_id,
        runs=runs,
    )
    return JSONResponse(content=diagnostics.to_camel_dict())


async def _build_json_response(
    agent_id: str,
    request_body: RunRequest,
    service: Any,
) -> JSONResponse:
    result = await service.trigger_run(agent_id, request_body)
    return JSONResponse(content=result.model_dump(by_alias=True))


async def _build_sse_response(
    agent_id: str,
    request_body: RunRequest,
    service: Any,
) -> StreamingResponse:
    """Build an SSE response for the run.

    The workflow is launched as a background task that pushes events
    into an ``asyncio.Queue``; the response generator yields those
    events as they arrive, so the SPA sees step-by-step progress
    rather than a single batch at the end of the run.
    """

    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    def _encode(event_name: str, payload: dict[str, Any]) -> bytes:
        body = f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
        return body.encode("utf-8")

    class _QueueSink:
        """Sink that forwards progress events into the response queue."""

        async def step_start(
            self,
            agent_id: str,
            step_name: str,
            step_type: str,
            iteration: int,
        ) -> None:
            await queue.put(
                (
                    "step-start",
                    {
                        "agentId": agent_id,
                        "stepName": step_name,
                        "stepType": step_type,
                        "iteration": iteration,
                    },
                )
            )

        async def step_complete(
            self,
            agent_id: str,
            step: Any,
            elapsed_ms: float,
        ) -> None:
            await queue.put(
                (
                    "step-complete",
                    {
                        "agentId": agent_id,
                        "step": (
                            step.to_dict() if hasattr(step, "to_dict") else step
                        ),
                        "elapsedMs": elapsed_ms,
                    },
                )
            )

        async def run_complete(self, run_result: Any) -> None:
            await queue.put(
                (
                    "run-complete",
                    (
                        run_result.to_dict()
                        if hasattr(run_result, "to_dict")
                        else run_result
                    ),
                )
            )

        async def iteration(
            self,
            agent_id: str,
            step_name: str,
            trace: Any,
        ) -> None:
            await queue.put(
                (
                    "agent-iteration",
                    {
                        "agentId": agent_id,
                        "stepName": step_name,
                        "iteration": getattr(trace, "iteration", 0),
                        "content": getattr(trace, "content", None),
                        "toolCallNames": list(
                            getattr(trace, "tool_call_names", []) or []
                        ),
                        "hasToolCalls": bool(
                            getattr(trace, "has_tool_calls", False)
                        ),
                        "timestamp": getattr(trace, "timestamp", None),
                    },
                )
            )

        async def tool_call(
            self,
            agent_id: str,
            step_name: str,
            tool_call: Any,
        ) -> None:
            await queue.put(
                (
                    "tool-call",
                    {
                        "agentId": agent_id,
                        "stepName": step_name,
                        "toolCall": (
                            tool_call.to_dict()
                            if hasattr(tool_call, "to_dict")
                            else tool_call
                        ),
                    },
                )
            )

    sink = _QueueSink()

    async def _run_workflow() -> None:
        try:
            await service.trigger_streaming_run(agent_id, request_body, sink)
        except AgentNotFoundError as exc:
            # Surface as an SSE error event so the client can render a
            # useful message instead of seeing the stream close silently.
            await queue.put(
                (
                    "error",
                    {
                        "eventType": "error",
                        "error": str(exc),
                        "recoverable": False,
                    },
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("streaming_run_failed", agent_id=agent_id)
            await queue.put(
                (
                    "error",
                    {
                        "eventType": "error",
                        "error": str(exc),
                        "recoverable": False,
                    },
                )
            )
        finally:
            # Sentinel that tells the generator to stop and propagate
            # any exception that landed on the task.
            await queue.put(None)

    workflow_task = asyncio.create_task(_run_workflow())

    async def event_iter():
        try:
            while True:
                event = await queue.get()
                if event is None:
                    # Re-raise any exception raised inside the task so
                    # Starlette surfaces a 500 instead of a clean 200.
                    if workflow_task.done() and workflow_task.exception():
                        raise workflow_task.exception()  # type: ignore[misc]
                    return
                event_name, payload = event
                yield _encode(event_name, payload)
        finally:
            if not workflow_task.done():
                workflow_task.cancel()
                try:
                    await workflow_task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
