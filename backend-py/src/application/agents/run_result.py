"""Agent run result models for diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AgentStepExecutionResult:
    """Result of a single step execution.

    Attributes:
        name: Step name
        type: Step type (agent, setVariables, echo)
        output: Step output
        input: Optional input to the step
        resolved_parameters: Resolved step parameters
        parameter_debug: Debug info for parameter resolution
        variable_debug: Debug info for variable assignment
        thread_context: JSON context data
        outcome: Outcome that was triggered
        next_step: Next step that was selected
        end_workflow: Whether workflow ended after this step
        tool_invocations: List of tool calls made during this step
        tool_error_detected: Whether a tool error occurred
    """

    name: str
    type: str
    output: str
    input: str | None = None
    resolved_parameters: dict[str, str] | None = None
    parameter_debug: dict[str, Any] | None = None
    variable_debug: dict[str, Any] | None = None
    thread_context: dict[str, Any] | None = None
    outcome: str | None = None
    next_step: str | None = None
    end_workflow: bool = False
    tool_invocations: list[AgentToolCall] = field(default_factory=list)
    tool_error_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "output": self.output,
            "input": self.input,
            "resolved_parameters": self.resolved_parameters,
            "parameter_debug": self.parameter_debug,
            "variable_debug": self.variable_debug,
            "thread_context": self.thread_context,
            "outcome": self.outcome,
            "next_step": self.next_step,
            "end_workflow": self.end_workflow,
            "tool_invocations": [t.to_dict() for t in self.tool_invocations],
            "tool_error_detected": self.tool_error_detected,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentStepExecutionResult:
        """Create from dictionary."""
        tool_invocations = [
            AgentToolCall.from_dict(t) for t in data.get("tool_invocations", [])
        ]
        return cls(
            name=data.get("name", ""),
            type=data.get("type", ""),
            output=data.get("output", ""),
            input=data.get("input"),
            resolved_parameters=data.get("resolved_parameters"),
            parameter_debug=data.get("parameter_debug"),
            variable_debug=data.get("variable_debug"),
            thread_context=data.get("thread_context"),
            outcome=data.get("outcome"),
            next_step=data.get("next_step"),
            end_workflow=data.get("end_workflow", False),
            tool_invocations=tool_invocations,
            tool_error_detected=data.get("tool_error_detected", False),
        )


@dataclass
class AgentToolCall:
    """Represents a tool invocation.

    Attributes:
        tool_name: Name of the tool called
        invocation_id: Unique ID for this invocation
        result: Result of the tool call
        arguments_json: JSON string of arguments
        error_message: Error message if failed
        error_details: Detailed error information
        error_code: Error code if failed
    """

    tool_name: str | None = None
    invocation_id: str | None = None
    result: str | None = None
    arguments_json: str | None = None
    error_message: str | None = None
    error_details: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "invocation_id": self.invocation_id,
            "result": self.result,
            "arguments_json": self.arguments_json,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "error_code": self.error_code,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentToolCall:
        """Create from dictionary."""
        return cls(
            tool_name=data.get("tool_name"),
            invocation_id=data.get("invocation_id"),
            result=data.get("result"),
            arguments_json=data.get("arguments_json"),
            error_message=data.get("error_message"),
            error_details=data.get("error_details"),
            error_code=data.get("error_code"),
        )


@dataclass
class AgentRunResult:
    """Result of an agent run.

    Attributes:
        agent_id: Agent definition ID
        status: Run status (completed, failed, etc.)
        steps: List of step execution results
        conversation_id: Conversation ID if applicable
        completed_at: When the run completed
    """

    agent_id: str
    status: str
    steps: list[AgentStepExecutionResult] = field(default_factory=list)
    conversation_id: str | None = None
    completed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "steps": [s.to_dict() for s in self.steps],
            "conversation_id": self.conversation_id,
            "completed_at": self.completed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentRunResult:
        """Create from dictionary."""
        completed_at = data.get("completed_at")
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at)
        elif completed_at is None:
            completed_at = datetime.utcnow()

        steps = [
            AgentStepExecutionResult.from_dict(s) for s in data.get("steps", [])
        ]
        return cls(
            agent_id=data.get("agent_id", ""),
            status=data.get("status", "unknown"),
            steps=steps,
            conversation_id=data.get("conversation_id"),
            completed_at=completed_at,
        )