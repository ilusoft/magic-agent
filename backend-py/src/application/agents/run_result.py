"""Agent run result models for diagnostics.

The dataclasses use ``snake_case`` field names internally for
ergonomics, but ``to_dict()`` serialises to the ``camelCase`` JSON
shape the SPA expects (matching the .NET backend's
``System.Text.Json`` defaults).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _camel(snake: str) -> str:
    """Convert ``snake_case`` to ``camelCase`` for one segment."""
    head, *rest = snake.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _camel_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Recursively remap ``snake_case`` keys to ``camelCase``."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            value = _camel_dict(value)
        elif isinstance(value, list):
            value = [
                _camel_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        out[_camel(key)] = value
    return out


def _fingerprint_api_key(api_key: str | None) -> str | None:
    """Return a short, non-reversible identifier for ``api_key``.

    The diagnostics payload must let operators confirm which credential
    was used without leaking the secret. We keep the trailing 4
    characters when an explicit key was provided so the SPA can still
    tell "Azure key A" apart from "Azure key B". ``None`` when the
    key was synthesised by the factory (e.g. the ``not-needed``
    placeholder used by OpenAI-compatible local servers).
    """
    if not api_key:
        return None
    if len(api_key) <= 4:
        return "***"
    return f"***{api_key[-4:]}"


@dataclass
class LLMCallConfig:
    """Resolved LLM configuration for a step.

    Captures *which* LLM was actually invoked so the diagnostics
    endpoint can prove a run hit the expected provider/model
    (e.g. local qwen vs. Azure OpenAI) without exposing secrets.

    Attributes:
        provider: LLM provider (``azure-openai``, ``openai``,
            ``openai-compatible``).
        model: Model name passed to the chat client.
        endpoint: Azure OpenAI endpoint, if applicable.
        base_url: Base URL for OpenAI-compatible providers.
        deployment: Azure OpenAI deployment name, if applicable.
        api_version: Azure OpenAI API version, if applicable.
        temperature: Sampling temperature, if set.
        max_tokens: Max output tokens, if set.
        api_key_fingerprint: Last 4 characters of the API key that
            was provided in the agent definition (``None`` when no
            key was supplied — e.g. local servers that accept any
            value).
    """

    provider: str
    model: str | None = None
    endpoint: str | None = None
    base_url: str | None = None
    deployment: str | None = None
    api_version: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    api_key_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to camelCase JSON-ready dict."""
        return _camel_dict(
            {
                "provider": self.provider,
                "model": self.model,
                "endpoint": self.endpoint,
                "base_url": self.base_url,
                "deployment": self.deployment,
                "api_version": self.api_version,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "api_key_fingerprint": self.api_key_fingerprint,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMCallConfig:
        """Create from dictionary."""
        return cls(
            provider=data.get("provider", ""),
            model=data.get("model"),
            endpoint=data.get("endpoint"),
            base_url=data.get("base_url"),
            deployment=data.get("deployment"),
            api_version=data.get("api_version"),
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
            api_key_fingerprint=data.get("api_key_fingerprint"),
        )


@dataclass
class AgentIterationTrace:
    """One LLM turn inside an agent step.

    Captures the assistant's text (when present) plus the tool calls
    it requested on that turn so the operator can see how the model
    reasoned its way to a final answer — including intermediate
    "thinking" turns where the model requested more tool calls before
    producing text. Mirrors the .NET ``AgentIterationTrace`` record
    and the ``agent-iteration`` SSE event emitted by
    ``StreamingAgentRunProgressSink``.

    Attributes:
        iteration: Zero-based index of the LLM turn within the
            step. The first assistant message is ``0``; subsequent
            assistant messages (after tool results) increment it.
        content: Assistant text produced on this turn. ``None`` for
            pure tool-call turns (the model only emitted function
            calls and is waiting for tool results).
        tool_call_names: Names of the tools the assistant requested
            on this turn, in order. Empty for the final text turn.
        has_tool_calls: Whether the assistant requested at least one
            tool on this turn. Mirrors the length of
            ``tool_call_names`` for caller convenience.
        timestamp: ISO-8601 timestamp of when the runner observed
            this iteration. Surfaced for ordering and for the
            timeline view in the SPA.
    """

    iteration: int
    content: str | None = None
    tool_call_names: list[str] = field(default_factory=list)
    has_tool_calls: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to camelCase JSON-ready dict."""
        return _camel_dict(
            {
                "iteration": self.iteration,
                "content": self.content,
                "tool_call_names": self.tool_call_names,
                "has_tool_calls": self.has_tool_calls,
                "timestamp": self.timestamp,
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentIterationTrace:
        """Create from dictionary."""
        return cls(
            iteration=data.get("iteration", 0),
            content=data.get("content"),
            tool_call_names=list(data.get("tool_call_names", []) or []),
            has_tool_calls=bool(data.get("has_tool_calls", False)),
            timestamp=data.get("timestamp") or datetime.utcnow().isoformat(),
        )


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
        iterations: Per-LLM-turn trace of the agent's reasoning —
            one entry per assistant message in the conversation,
            capturing the assistant's text (when present) and the
            tool calls it requested on that turn. Populated for
            ``type == "agent"`` steps; ``[]`` for ``setVariables``/
            ``echo``. Mirrors the .NET
            ``AgentStepExecutionResult.Iterations`` field and the
            ``agent-iteration`` SSE event so the SPA can render the
            model turning over tool calls in real time.
        tool_error_detected: Whether a tool error occurred
        llm_config: Snapshot of the LLM that handled this step. Only
            populated for ``type == "agent"`` steps; ``None`` for
            ``setVariables``/``echo``. Surfaces provider/model/
            endpoint/base_url in the diagnostics endpoint so operators
            can verify the expected backend (e.g. local qwen vs.
            Azure OpenAI) was actually called.
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
    iterations: list[AgentIterationTrace] = field(default_factory=list)
    tool_error_detected: bool = False
    llm_config: LLMCallConfig | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to camelCase JSON-ready dict.

        Matches the .NET ``AgentStepExecutionResult`` serialisation
        (camelCase property names) so the SPA's
        ``AgentStepExecutionResult`` TypeScript interface lines up
        with the wire payload.
        """
        return _camel_dict(
            {
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
                "iterations": [it.to_dict() for it in self.iterations],
                "tool_error_detected": self.tool_error_detected,
                "llm_config": (
                    self.llm_config.to_dict() if self.llm_config else None
                ),
            }
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentStepExecutionResult:
        """Create from dictionary."""
        tool_invocations = [
            AgentToolCall.from_dict(t) for t in data.get("tool_invocations", [])
        ]
        iterations = [
            AgentIterationTrace.from_dict(it)
            for it in data.get("iterations", [])
        ]
        llm_config_data = data.get("llm_config")
        llm_config = (
            LLMCallConfig.from_dict(llm_config_data)
            if isinstance(llm_config_data, dict)
            else None
        )
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
            iterations=iterations,
            tool_error_detected=data.get("tool_error_detected", False),
            llm_config=llm_config,
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
        """Convert to camelCase JSON-ready dict."""
        return _camel_dict(
            {
                "tool_name": self.tool_name,
                "invocation_id": self.invocation_id,
                "result": self.result,
                "arguments_json": self.arguments_json,
                "error_message": self.error_message,
                "error_details": self.error_details,
                "error_code": self.error_code,
            }
        )

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
        """Convert to camelCase JSON-ready dict.

        Matches the .NET ``AgentRunResult`` serialisation so the SPA
        can read ``agentId``/``conversationId``/``completedAt``
        directly off the SSE ``run-complete`` payload.
        """
        return _camel_dict(
            {
                "agent_id": self.agent_id,
                "status": self.status,
                "steps": [s.to_dict() for s in self.steps],
                "conversation_id": self.conversation_id,
                "completed_at": self.completed_at.isoformat(),
            }
        )

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