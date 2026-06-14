"""Conversation store interface and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import structlog

from src.application.agents.message import AgentMessage

logger = structlog.get_logger(__name__)


class IAgentConversationStore(ABC):
    """Interface for conversation message persistence.

    Implementations can use in-memory storage, file-based storage,
    or external services like Redis, database, etc.
    """

    @abstractmethod
    async def get_messages(
        self,
        conversation_id: str,
    ) -> list[AgentMessage]:
        """Get all messages for a conversation.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            List of messages in chronological order
        """
        ...

    @abstractmethod
    async def save_messages(
        self,
        conversation_id: str,
        messages: list[AgentMessage],
    ) -> None:
        """Save messages for a conversation.

        Args:
            conversation_id: Unique conversation identifier
            messages: Messages to save
        """
        ...

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: Unique conversation identifier
        """
        ...

    @abstractmethod
    async def conversation_exists(self, conversation_id: str) -> bool:
        """Check if a conversation exists.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            True if conversation exists
        """
        ...


class InMemoryAgentConversationStore(IAgentConversationStore):
    """In-memory conversation store.

    Suitable for development and single-instance deployments.
    Messages are lost on application restart.
    """

    def __init__(self) -> None:
        """Initialize the store."""
        self._conversations: dict[str, list[AgentMessage]] = {}

    async def get_messages(
        self,
        conversation_id: str,
    ) -> list[AgentMessage]:
        """Get all messages for a conversation.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            List of messages in chronological order
        """
        messages = self._conversations.get(conversation_id, [])
        # Return a copy to prevent external modification
        return [AgentMessage(m.role, m.content, m.timestamp) for m in messages]

    async def save_messages(
        self,
        conversation_id: str,
        messages: list[AgentMessage],
    ) -> None:
        """Save messages for a conversation.

        Args:
            conversation_id: Unique conversation identifier
            messages: Messages to save
        """
        # Store a copy to prevent external modification
        self._conversations[conversation_id] = [
            AgentMessage(m.role, m.content, m.timestamp) for m in messages
        ]
        logger.debug("messages_saved", conversation_id=conversation_id, count=len(messages))

    async def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: Unique conversation identifier
        """
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            logger.debug("conversation_deleted", conversation_id=conversation_id)

    async def conversation_exists(self, conversation_id: str) -> bool:
        """Check if a conversation exists.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            True if conversation exists
        """
        return conversation_id in self._conversations


class ConversationContext:
    """Context for managing a single conversation.

    Wraps the conversation store and provides a clean interface
    for managing messages within a workflow execution.
    """

    def __init__(
        self,
        store: IAgentConversationStore,
        enabled: bool,
        conversation_id: str | None,
        messages: list[AgentMessage],
    ) -> None:
        """Initialize conversation context.

        Args:
            store: Conversation store
            enabled: Whether conversation is enabled
            conversation_id: Conversation ID (generated if enabled and not provided)
            messages: Existing messages to start with
        """
        self._store = store
        self._enabled = enabled
        self._conversation_id = conversation_id
        self._messages = list(messages)

    @property
    def enabled(self) -> bool:
        """Check if conversation is enabled."""
        return self._enabled

    @property
    def conversation_id(self) -> str | None:
        """Get the conversation ID."""
        return self._conversation_id

    @property
    def messages(self) -> list[AgentMessage]:
        """Get current messages."""
        return list(self._messages)

    @classmethod
    async def create(
        cls,
        store: IAgentConversationStore,
        step: dict[str, Any],
        conversation_id: str | None,
    ) -> ConversationContext:
        """Create a conversation context from a step definition.

        Args:
            store: Conversation store
            step: Step definition with optional 'conversation' config
            conversation_id: Optional existing conversation ID

        Returns:
            New ConversationContext instance
        """
        conversation_config = step.get("conversation", {})
        enabled = conversation_config.get("enabled", False) if conversation_config else False

        active_conversation_id = conversation_id
        messages: list[AgentMessage] = []

        if enabled:
            if not active_conversation_id:
                import uuid
                active_conversation_id = uuid.uuid4().hex

            # Load existing messages
            messages = await store.get_messages(active_conversation_id)

        return cls(
            store=store,
            enabled=enabled,
            conversation_id=active_conversation_id,
            messages=messages,
        )

    async def add_message(self, message: AgentMessage) -> None:
        """Add a message to the conversation.

        Args:
            message: Message to add
        """
        if not self._enabled or not self._conversation_id:
            return

        self._messages.append(message)

    async def add_user_message(self, content: str) -> AgentMessage:
        """Add a user message.

        Args:
            content: Message content

        Returns:
            The created message
        """
        message = AgentMessage(role="user", content=content)
        await self.add_message(message)
        return message

    async def add_assistant_message(self, content: str) -> AgentMessage:
        """Add an assistant message.

        Args:
            content: Message content

        Returns:
            The created message
        """
        message = AgentMessage(role="assistant", content=content)
        await self.add_message(message)
        return message

    async def save(self) -> None:
        """Save current messages to the store."""
        if not self._enabled or not self._conversation_id:
            return

        await self._store.save_messages(self._conversation_id, self._messages)

    def to_langchain_messages(self) -> list[Any]:
        """Convert all messages to LangChain format.

        Returns:
            List of LangChain messages
        """
        return [msg.to_langchain_message() for msg in self._messages]


# Global store instance
_conversation_store: IAgentConversationStore | None = None


def get_conversation_store() -> IAgentConversationStore:
    """Get the global conversation store singleton."""
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = InMemoryAgentConversationStore()
    return _conversation_store


def set_conversation_store(store: IAgentConversationStore) -> None:
    """Set the global conversation store (for testing)."""
    global _conversation_store
    _conversation_store = store