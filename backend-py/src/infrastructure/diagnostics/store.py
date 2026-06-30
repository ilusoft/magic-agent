"""Diagnostics store for agent run history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import structlog

from src.application.agents.run_result import AgentRunResult, AgentStepExecutionResult

logger = structlog.get_logger(__name__)


class IAgentDiagnosticsStore(ABC):
    """Interface for run diagnostics persistence.

    Implementations can use in-memory storage, file-based storage,
    or external services.
    """

    @abstractmethod
    async def save_run(
        self,
        conversation_id: str,
        run_result: AgentRunResult,
    ) -> None:
        """Save a run result.

        Args:
            conversation_id: Conversation/run identifier
            run_result: The run result to save
        """
        ...

    @abstractmethod
    async def get_runs(
        self,
        conversation_id: str,
    ) -> list[AgentRunResult]:
        """Get all runs for a conversation.

        Args:
            conversation_id: Conversation/run identifier

        Returns:
            List of run results in chronological order
        """
        ...


class InMemoryAgentDiagnosticsStore(IAgentDiagnosticsStore):
    """In-memory diagnostics store.

    Suitable for development and single-instance deployments.
    Data is lost on application restart.
    """

    def __init__(self) -> None:
        """Initialize the store."""
        self._runs: dict[str, list[AgentRunResult]] = {}

    async def save_run(
        self,
        conversation_id: str,
        run_result: AgentRunResult,
    ) -> None:
        """Save a run result.

        Args:
            conversation_id: Conversation/run identifier
            run_result: The run result to save
        """
        if not conversation_id:
            return

        # Make a copy to prevent external modification
        steps_copy = [
            AgentStepExecutionResult(
                name=s.name,
                type=s.type,
                output=s.output,
                input=s.input,
                resolved_parameters=s.resolved_parameters,
                parameter_debug=s.parameter_debug,
                variable_debug=s.variable_debug,
                thread_context=s.thread_context,
                outcome=s.outcome,
                next_step=s.next_step,
                end_workflow=s.end_workflow,
                tool_invocations=s.tool_invocations,
                tool_error_detected=s.tool_error_detected,
                llm_config=s.llm_config,
            )
            for s in run_result.steps
        ]
        run_copy = AgentRunResult(
            agent_id=run_result.agent_id,
            status=run_result.status,
            steps=steps_copy,
            conversation_id=run_result.conversation_id,
            completed_at=run_result.completed_at,
        )

        if conversation_id not in self._runs:
            self._runs[conversation_id] = []

        self._runs[conversation_id].append(run_copy)
        logger.debug("run_saved", conversation_id=conversation_id, agent_id=run_result.agent_id)

    async def get_runs(
        self,
        conversation_id: str,
    ) -> list[AgentRunResult]:
        """Get all runs for a conversation.

        Args:
            conversation_id: Conversation/run identifier

        Returns:
            List of run results in chronological order
        """
        if not conversation_id:
            return []

        runs = self._runs.get(conversation_id, [])
        # Return copies
        return [
            AgentRunResult(
                agent_id=r.agent_id,
                status=r.status,
                steps=r.steps,
                conversation_id=r.conversation_id,
                completed_at=r.completed_at,
            )
            for r in runs
        ]


# Global store instance
_diagnostics_store: IAgentDiagnosticsStore | None = None


def get_diagnostics_store() -> IAgentDiagnosticsStore:
    """Get the global diagnostics store singleton."""
    global _diagnostics_store
    if _diagnostics_store is None:
        _diagnostics_store = InMemoryAgentDiagnosticsStore()
    return _diagnostics_store


def set_diagnostics_store(store: IAgentDiagnosticsStore) -> None:
    """Set the global diagnostics store (for testing)."""
    global _diagnostics_store
    _diagnostics_store = store