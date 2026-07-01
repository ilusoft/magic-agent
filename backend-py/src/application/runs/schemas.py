"""Run schemas using Pydantic.

The non-streaming JSON response and the diagnostics payload mirror
the .NET backend's ``AgentWorkflowResult`` /
``AgentConversationDiagnostics`` shapes (``agentId``/``status``/
``lastStep``/``conversationId``) so the same SPA client works
against either backend without branching.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.application.agents.run_result import AgentRunResult


class RunRequest(BaseModel):
    """Request to trigger an agent run.

    The SPA sends ``conversationId`` (camelCase) on follow-up turns
    so multi-round conversations reuse the same conversation context;
    the schema therefore accepts both the camelCase alias and the
    snake_case field name (``populate_by_name=True``). Without the
    alias Pydantic v2 silently drops the unknown field and every
    round is treated as a fresh conversation.
    """

    model_config = ConfigDict(populate_by_name=True)

    input: str = Field(description="User input to the agent")
    conversation_id: str | None = Field(
        default=None,
        alias="conversationId",
        description="Conversation ID forwarded by the SPA on follow-up turns",
    )
    parameters: dict[str, Any] = Field(default_factory=dict, description="Run parameters")


class AgentStepResult(BaseModel):
    """Lightweight step summary returned in the non-streaming JSON.

    Mirrors the subset of ``AgentStepExecutionResult`` that the SPA
    actually consumes from the non-streaming response.
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    type: str
    output: str = ""
    outcome: str | None = None
    next_step: str | None = Field(default=None, alias="nextStep")
    end_workflow: bool = Field(default=False, alias="endWorkflow")


class AgentWorkflowResult(BaseModel):
    """Non-streaming JSON response.

    Shape matches the .NET backend's ``AgentWorkflowResult`` record
    (see ``backend/src/MagicAgent.Api/Controllers/AgentRunsController.cs``)
    so the SPA's ``AgentRunnerView`` can read ``lastStep.output`` and
    ``conversationId`` regardless of which backend is selected.
    """

    model_config = ConfigDict(populate_by_name=True)

    agent_id: str = Field(alias="agentId")
    status: str
    last_step: AgentStepResult | None = Field(default=None, alias="lastStep")
    conversation_id: str | None = Field(default=None, alias="conversationId")


class AgentConversationDiagnostics(BaseModel):
    """Diagnostics payload returned by the debug endpoint.

    Mirrors the .NET ``AgentConversationDiagnostics`` record so the
    SPA's ``loadDiagnostics`` call can read ``conversationId`` and
    ``runs[*]`` (``agentId``/``status``/``steps``/``completedAt``)
    without knowing which backend produced the response.
    """

    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str = Field(alias="conversationId")
    runs: list[AgentRunResult] = Field(
        default_factory=list,
        description="All runs recorded for the conversation, in chronological order.",
    )

    def to_camel_dict(self) -> dict[str, Any]:
        """Serialise to the camelCase JSON shape the SPA expects.

        ``AgentRunResult.to_dict()`` already returns camelCase, so
        we only need to remap this model's own fields.
        """
        from src.application.agents.run_result import _camel_dict

        return _camel_dict(
            {
                "conversation_id": self.conversation_id,
                "runs": [r.to_dict() for r in self.runs],
            }
        )


class StepProgressEvent(BaseModel):
    """Progress event for a single step."""

    step_id: str = Field(description="Step ID")
    step_type: str = Field(description="Step type")
    status: str = Field(description="Status (start, complete, error)")
    output: Any | None = Field(default=None, description="Step output")
    duration_ms: int | None = Field(default=None, description="Step duration")
    error: str | None = Field(default=None, description="Error message if any")


class RunProgressEvent(BaseModel):
    """Progress event for a run."""

    event_type: str = Field(description="Event type (step_start, step_complete, iteration, error, complete)")
    run_id: str | None = Field(default=None, description="Run ID")
    iteration: int | None = Field(default=None, description="Current iteration")
    max_iterations: int | None = Field(default=None, description="Max iterations")
    step: StepProgressEvent | None = Field(default=None, description="Step progress")
    final_output: str | None = Field(default=None, description="Final output on complete")
    total_duration_ms: int | None = Field(default=None, description="Total duration on complete")
    error: str | None = Field(default=None, description="Error message")
    recoverable: bool | None = Field(default=None, description="Whether error is recoverable")