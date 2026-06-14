"""Agent message model for conversation history."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass
class AgentMessage:
    """A message in a conversation.

    Attributes:
        role: Message role ('user' or 'assistant')
        content: Message content
        timestamp: When the message was created
    """

    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.utcnow()
        role_value = data.get("role", "user")
        return cls(
            role=role_value if role_value in ("user", "assistant") else "user",
            content=data.get("content", ""),
            timestamp=timestamp,
        )

    def to_langchain_message(self) -> Any:
        """Convert to LangChain message."""
        from langchain_core.messages import HumanMessage, AIMessage

        if self.role == "user":
            return HumanMessage(content=self.content)
        return AIMessage(content=self.content)

    @classmethod
    def from_langchain_message(cls, msg: Any) -> AgentMessage:
        """Create from LangChain message."""
        from langchain_core.messages import HumanMessage, AIMessage

        role: Literal["user", "assistant"] = "user"
        if isinstance(msg, AIMessage):
            role = "assistant"
        return cls(
            role=role,
            content=getattr(msg, "content", str(msg)),
            timestamp=getattr(msg, "response_metadata", {}).get("timestamp", datetime.utcnow())
            if hasattr(msg, "response_metadata") else datetime.utcnow(),
        )