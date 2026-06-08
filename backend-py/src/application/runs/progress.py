"""Run progress events for SSE streaming."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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

    event_type: str = Field(description="Event type")
    run_id: str | None = Field(default=None, description="Run ID")
    iteration: int | None = Field(default=None, description="Current iteration")
    max_iterations: int | None = Field(default=None, description="Max iterations")
    step: StepProgressEvent | None = Field(default=None, description="Step progress")
    final_output: str | None = Field(default=None, description="Final output on complete")
    total_duration_ms: int | None = Field(default=None, description="Total duration on complete")
    error: str | None = Field(default=None, description="Error message")
    recoverable: bool | None = Field(default=None, description="Whether error is recoverable")


async def step_start_event(
    run_id: str,
    step_id: str,
    step_type: str,
    iteration: int,
    max_iterations: int,
) -> RunProgressEvent:
    """Create a step start event."""
    return RunProgressEvent(
        event_type="step_start",
        run_id=run_id,
        iteration=iteration,
        max_iterations=max_iterations,
        step=StepProgressEvent(
            step_id=step_id,
            step_type=step_type,
            status="start",
        ),
    )


async def step_complete_event(
    run_id: str,
    step_id: str,
    step_type: str,
    output: Any,
    duration_ms: int,
    iteration: int,
    max_iterations: int,
) -> RunProgressEvent:
    """Create a step complete event."""
    return RunProgressEvent(
        event_type="step_complete",
        run_id=run_id,
        iteration=iteration,
        max_iterations=max_iterations,
        step=StepProgressEvent(
            step_id=step_id,
            step_type=step_type,
            status="complete",
            output=output,
            duration_ms=duration_ms,
        ),
    )


async def error_event(
    run_id: str,
    message: str,
    recoverable: bool,
    iteration: int | None = None,
    max_iterations: int | None = None,
) -> RunProgressEvent:
    """Create an error event."""
    return RunProgressEvent(
        event_type="error",
        run_id=run_id,
        iteration=iteration,
        max_iterations=max_iterations,
        error=message,
        recoverable=recoverable,
    )


async def complete_event(
    run_id: str,
    final_output: str,
    total_duration_ms: int,
    max_iterations: int,
) -> RunProgressEvent:
    """Create a complete event."""
    return RunProgressEvent(
        event_type="complete",
        run_id=run_id,
        max_iterations=max_iterations,
        final_output=final_output,
        total_duration_ms=total_duration_ms,
    )