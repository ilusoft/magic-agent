"""Run schemas using Pydantic."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Request to trigger an agent run."""

    input: str = Field(description="User input to the agent")
    conversation_id: str | None = Field(default=None, description="Conversation ID")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Run parameters")


class RunResponse(BaseModel):
    """Response from a synchronous agent run."""

    run_id: str = Field(description="Unique run identifier")
    status: str = Field(description="Run status")
    output: str | None = Field(default=None, description="Agent output")
    duration_ms: int | None = Field(default=None, description="Execution duration")


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