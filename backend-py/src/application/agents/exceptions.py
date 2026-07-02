"""Agent application service exceptions."""

from __future__ import annotations


class AgentNotFoundError(Exception):
    """Raised when an agent is not found."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent not found: {agent_id}")


class AgentValidationError(Exception):
    """Raised when agent definition validation fails."""

    def __init__(self, message: str, issues: list[str] | None = None) -> None:
        self.issues = issues or [message]
        super().__init__(message)