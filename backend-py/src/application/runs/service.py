"""Agent runs service - handles run execution.

The non-streaming response shape mirrors the .NET backend's
``AgentWorkflowResult`` record (``agentId``/``status``/``lastStep``/
``conversationId``) so the SPA can treat both backends as
interchangeable.
"""

from __future__ import annotations

import structlog
from typing import Any

from src.application.agents.run_result import (
    AgentRunResult,
    AgentStepExecutionResult,
)
from src.application.runs.schemas import (
    AgentStepResult,
    AgentWorkflowResult,
    RunRequest,
)
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

    @staticmethod
    def _merge_default_parameters(
        agent_def: dict[str, Any],
        request: RunRequest,
    ) -> dict[str, Any]:
        """Merge agent defaults with caller-supplied parameters."""
        defaults = {
            **agent_def.get("default_parameters", {}),
            **agent_def.get("defaultParameters", {}),
        }
        return {**defaults, **(request.parameters or {})}

    def _build_workflow_result(
        self,
        run_result: AgentRunResult,
    ) -> AgentWorkflowResult:
        """Convert an ``AgentRunResult`` into the non-streaming JSON.

        Picks the last step as ``lastStep`` (matching .NET's behaviour
        and the SPA's ``result.lastStep?.output`` access pattern).
        """
        last_step: AgentStepResult | None = None
        if run_result.steps:
            tail = run_result.steps[-1]
            last_step = AgentStepResult(
                name=tail.name,
                type=tail.type,
                output=tail.output,
                outcome=tail.outcome,
                next_step=tail.next_step,
                end_workflow=tail.end_workflow,
            )

        return AgentWorkflowResult(
            agent_id=run_result.agent_id,
            status=run_result.status,
            last_step=last_step,
            conversation_id=run_result.conversation_id,
        )

    async def trigger_run(
        self,
        agent_id: str,
        request: RunRequest,
    ) -> AgentWorkflowResult:
        """Trigger a synchronous agent run.

        Returns:
            The non-streaming JSON response in the .NET-compatible
            ``AgentWorkflowResult`` shape.
        """
        agent_def = await self._provider.load_agent(agent_id)
        if not agent_def:
            from src.application.agents.exceptions import AgentNotFoundError
            raise AgentNotFoundError(agent_id)

        parameters = self._merge_default_parameters(agent_def, request)

        # ``execute_stream`` with a no-op sink is the cheapest path
        # because it shares the streaming code path that knows how to
        # resolve LLM credentials and MCP tools correctly.
        from src.agent_runtime.progress_sink import NoOpProgressSink

        run_result = await self._executor.execute_stream(
            agent_definition=agent_def,
            input_text=request.input,
            parameters=parameters,
            progress_sink=NoOpProgressSink(),
        )
        return self._build_workflow_result(run_result)

    async def trigger_streaming_run(
        self,
        agent_id: str,
        request: RunRequest,
        progress_sink: Any,
    ) -> AgentRunResult:
        """Trigger a streaming agent run.

        Unlike the previous implementation, the route layer is
        responsible for translating sink events into wire bytes; this
        service just runs the workflow and forwards to the sink.

        Args:
            agent_id: Agent identifier
            request: Run request
            progress_sink: ``AgentRunProgressSink``-compatible object
                (typically ``SseProgressSink`` when wired to a real
                HTTP response).

        Returns:
            The final ``AgentRunResult``.
        """
        agent_def = await self._provider.load_agent(agent_id)
        if not agent_def:
            from src.application.agents.exceptions import AgentNotFoundError
            raise AgentNotFoundError(agent_id)

        parameters = self._merge_default_parameters(agent_def, request)

        return await self._executor.execute_stream(
            agent_definition=agent_def,
            input_text=request.input,
            parameters=parameters,
            progress_sink=progress_sink,
        )


# Singleton
_runs_service: AgentRunsService | None = None


def get_runs_service() -> AgentRunsService:
    """Get the runs service singleton."""
    global _runs_service
    if _runs_service is None:
        _runs_service = AgentRunsService()
    return _runs_service
