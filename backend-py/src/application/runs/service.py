"""Agent runs service - handles run execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator

from src.application.runs.schemas import RunRequest, RunResponse
from src.agent_runtime.executor import AgentExecutor

if TYPE_CHECKING:
    pass


class AgentRunsService:
    """Service for managing agent runs."""

    def __init__(self, provider: Any) -> None:
        """Initialize with a provider (for compatibility)."""
        self._provider = provider
        self._executor = AgentExecutor()

    async def trigger_run(
        self, agent_id: str, request: RunRequest
    ) -> RunResponse:
        """Trigger a synchronous agent run.

        Args:
            agent_id: Agent identifier
            request: Run request

        Returns:
            Run response
        """
        # This is handled directly in the route for now
        # to have access to all dependencies
        raise NotImplementedError("Use route handler directly")

    async def trigger_streaming_run(
        self, agent_id: str, request: RunRequest
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Trigger a streaming agent run, returns async generator.

        Args:
            agent_id: Agent identifier
            request: Run request

        Yields:
            Progress events
        """
        # This is handled directly in the route for now
        raise NotImplementedError("Use route handler directly")