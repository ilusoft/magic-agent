"""Agent run execution endpoints (sync and SSE streaming)."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from src.application.runs.schemas import RunRequest, RunResponse
from src.application.runs.service import get_runs_service
from src.application.agents.exceptions import AgentNotFoundError

router = APIRouter()


@router.post("/{agent_id}/runs")
async def trigger_agent_run(
    agent_id: str,
    request: RunRequest,
) -> RunResponse:
    """Trigger a synchronous agent run.

    Args:
        agent_id: Agent identifier
        request: Run request with input and parameters

    Returns:
        Run response with output
    """
    service = get_runs_service()

    try:
        result = await service.trigger_run(agent_id, request)
        return result
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{agent_id}/runs/stream")
async def stream_agent_run(
    agent_id: str,
    request: RunRequest,
) -> StreamingResponse:
    """Trigger a streaming agent run (SSE).

    Args:
        agent_id: Agent identifier
        request: Run request with input and parameters

    Returns:
        SSE stream of progress events
    """
    service = get_runs_service()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in service.trigger_streaming_run(agent_id, request):
                yield f"data: {json.dumps(event)}\n\n"
        except AgentNotFoundError as e:
            error_event = {
                "event_type": "error",
                "error": str(e),
                "recoverable": False,
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        except Exception as e:
            error_event = {
                "event_type": "error",
                "error": str(e),
                "recoverable": False,
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )