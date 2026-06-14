"""Agent runs service - handles run execution."""

from __future__ import annotations

from typing import Any, AsyncGenerator

import structlog

from src.application.runs.schemas import RunRequest, RunResponse
from src.agent_runtime.workflow_executor import WorkflowExecutor, get_workflow_executor
from src.config import get_settings
from src.infrastructure.persistence.file_provider import FileAgentDefinitionsProvider

logger = structlog.get_logger(__name__)


class AgentRunsService:
    """Service for managing agent runs.

    Orchestrates workflow execution by:
    1. Loading agent definitions from the provider
    2. Merging default parameters with request parameters
    3. Delegating to WorkflowExecutor for execution
    4. Returning structured responses
    """

    def __init__(
        self,
        provider: FileAgentDefinitionsProvider | None = None,
        executor: WorkflowExecutor | None = None,
    ) -> None:
        """Initialize with optional provider and executor.

        Args:
            provider: File agent definitions provider
            executor: Workflow executor
        """
        settings = get_settings()
        self._provider = provider or FileAgentDefinitionsProvider(settings.configs_path)
        self._executor = executor or get_workflow_executor()

    async def trigger_run(
        self,
        agent_id: str,
        request: RunRequest,
    ) -> RunResponse:
        """Trigger a synchronous agent run.

        Args:
            agent_id: Agent identifier
            request: Run request with input and parameters

        Returns:
            Run response with output and metadata

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        # Load agent definition
        agent_def = await self._provider.load_agent(agent_id)
        if not agent_def:
            from src.application.agents.exceptions import AgentNotFoundError
            raise AgentNotFoundError(agent_id)

        # Merge default parameters with request parameters
        parameters = {**agent_def.get("default_parameters", {}), **(request.parameters or {})}

        # Execute workflow
        result = await self._executor.execute(
            agent_definition=agent_def,
            input_text=request.input,
            parameters=parameters,
        )

        return RunResponse(
            run_id=result["run_id"],
            status=result["status"],
            output=result.get("output"),
            duration_ms=result.get("duration_ms"),
        )

    async def trigger_streaming_run(
        self,
        agent_id: str,
        request: RunRequest,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Trigger a streaming agent run.

        Args:
            agent_id: Agent identifier
            request: Run request with input and parameters

        Yields:
            Progress events (step_start, step_complete, error, complete)

        Raises:
            AgentNotFoundError: If agent doesn't exist
        """
        # Load agent definition
        agent_def = await self._provider.load_agent(agent_id)
        if not agent_def:
            from src.application.agents.exceptions import AgentNotFoundError
            raise AgentNotFoundError(agent_id)

        # Merge default parameters with request parameters
        parameters = {**agent_def.get("default_parameters", {}), **(request.parameters or {})}

        # Stream execution events
        async for event in self._executor.execute_stream(
            agent_definition=agent_def,
            input_text=request.input,
            parameters=parameters,
        ):
            yield event


# Singleton
_runs_service: AgentRunsService | None = None


def get_runs_service() -> AgentRunsService:
    """Get the runs service singleton."""
    global _runs_service
    if _runs_service is None:
        _runs_service = AgentRunsService()
    return _runs_service