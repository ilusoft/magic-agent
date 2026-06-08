"""Agent run execution endpoints (sync and SSE streaming)."""

from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from src.application.runs.schemas import RunRequest, RunResponse
from src.application.runs.service import AgentRunsService
from src.application.runs.progress import (
    step_start_event,
    step_complete_event,
    error_event,
    complete_event,
)
from src.application.agents.exceptions import AgentNotFoundError
from src.config import get_settings
from src.infrastructure.persistence.file_provider import FileAgentDefinitionsProvider
from src.agent_runtime.executor import get_agent_executor

router = APIRouter()


def get_runs_service() -> AgentRunsService:
    """Get agent runs service instance."""
    settings = get_settings()
    provider = FileAgentDefinitionsProvider(settings.configs_path)
    return AgentRunsService(provider)


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
    settings = get_settings()
    provider = FileAgentDefinitionsProvider(settings.configs_path)

    # Load agent definition
    agent_def = await provider.load_agent(agent_id)
    if not agent_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )

    # Get LLM config
    llm_config = agent_def.get("llm", {})
    if not llm_config.get("api_key"):
        llm_config["api_key"] = settings.llm_api_key
    if not llm_config.get("endpoint"):
        llm_config["endpoint"] = settings.llm_endpoint
    if not llm_config.get("deployment"):
        llm_config["deployment"] = settings.llm_deployment

    # Get tools
    tools = []
    for tool_def in agent_def.get("tools", []):
        if tool_def.get("type") == "http":
            from src.infrastructure.mcp.tool_builder import ToolBuilder
            tool = ToolBuilder.from_http_definition(tool_def)
            if tool:
                tools.append(tool)

    # Execute
    executor = get_agent_executor()
    result = await executor.execute(
        input_text=request.input,
        llm_config=llm_config,
        tools=tools if tools else None,
        system_prompt=agent_def.get("system_prompt"),
        max_iterations=agent_def.get("runtime", {}).get("max_iterations", settings.max_iterations),
        initial_context=request.parameters,
    )

    return RunResponse(
        run_id=result["run_id"],
        status=result["status"],
        output=result.get("output"),
        duration_ms=result.get("duration_ms"),
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
    settings = get_settings()
    provider = FileAgentDefinitionsProvider(settings.configs_path)

    # Load agent definition
    agent_def = await provider.load_agent(agent_id)
    if not agent_def:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )

    run_id = str(uuid.uuid4())

    async def event_generator() -> AsyncGenerator[str, None]:
        # Get LLM config
        llm_config = agent_def.get("llm", {})
        if not llm_config.get("api_key"):
            llm_config["api_key"] = settings.llm_api_key
        if not llm_config.get("endpoint"):
            llm_config["endpoint"] = settings.llm_endpoint
        if not llm_config.get("deployment"):
            llm_config["deployment"] = settings.llm_deployment

        # Get tools
        tools = []
        for tool_def in agent_def.get("tools", []):
            if tool_def.get("type") == "http":
                from src.infrastructure.mcp.tool_builder import ToolBuilder
                tool = ToolBuilder.from_http_definition(tool_def)
                if tool:
                    tools.append(tool)

        # Emit start
        yield f"data: {json.dumps({'event_type': 'start', 'run_id': run_id})}\n\n"

        # Execute with streaming
        executor = get_agent_executor()

        try:
            async for event in executor.execute_stream(
                input_text=request.input,
                llm_config=llm_config,
                tools=tools if tools else None,
                system_prompt=agent_def.get("system_prompt"),
                max_iterations=agent_def.get("runtime", {}).get("max_iterations", settings.max_iterations),
                initial_context=request.parameters,
            ):
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            error = {
                "event_type": "error",
                "run_id": run_id,
                "error": str(e),
                "recoverable": False,
            }
            yield f"data: {json.dumps(error)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )