"""Agent service - business logic for agent CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.application.agents.exceptions import AgentNotFoundError, AgentValidationError
from src.application.agents.schemas import AgentDefinition
from src.infrastructure.persistence.file_provider import FileAgentDefinitionsProvider

class AgentService:
    """Service for managing agent definitions."""

    def __init__(self, provider: FileAgentDefinitionsProvider) -> None:
        self._provider = provider

    async def get_agent(self, agent_id: str) -> AgentDefinition:
        """Get an agent definition by ID.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent definition

        Raises:
            AgentNotFoundError: If agent not found
        """
        data = await self._provider.load_agent(agent_id)
        if not data:
            raise AgentNotFoundError(agent_id)

        # Handle wrapped format
        if "agent" in data:
            data = data["agent"]

        return AgentDefinition(**data)

    async def list_agents(self) -> list[AgentDefinition]:
        """List all agent definitions.

        Returns:
            List of agent definitions
        """
        agents = await self._provider.list_agents()
        result = []

        for agent_data in agents:
            if "agent" in agent_data:
                agent_data = agent_data["agent"]
            try:
                result.append(AgentDefinition(**agent_data))
            except Exception:
                # Skip invalid agents
                continue

        return result

    async def upsert_agent(
        self, agent_id: str, definition: AgentDefinition
    ) -> AgentDefinition:
        """Create or update an agent definition.

        Args:
            agent_id: Agent identifier
            definition: Agent definition

        Returns:
            Saved agent definition
        """
        # Validate
        try:
            data = definition.model_dump(exclude_none=True)
        except Exception as e:
            raise AgentValidationError(str(e))

        # Save
        await self._provider.save_agent(agent_id, data)
        return definition

    async def delete_agent(self, agent_id: str) -> None:
        """Delete an agent definition.

        Args:
            agent_id: Agent identifier

        Raises:
            AgentNotFoundError: If agent not found
        """
        deleted = await self._provider.delete_agent(agent_id)
        if not deleted:
            raise AgentNotFoundError(agent_id)