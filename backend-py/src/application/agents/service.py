"""Agent service - business logic for agent CRUD operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.application.agents.exceptions import AgentNotFoundError, AgentValidationError
from src.application.agents.schemas import AgentDefinition
from src.application.agents.validator import validate_document
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

    async def get_full_document(self) -> dict[str, Any]:
        """Get the full agent definitions document.

        Returns the raw document with all metadata preserved
        (agents array, viewLayout, streaming config, etc.).

        Returns:
            Full agent definitions document
        """
        return await self._provider.get_full_document()

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

    async def save_full_document(self, document: dict[str, Any]) -> dict[str, Any]:
        """Save the full agent definitions document.

        Args:
            document: Full agent definitions document with agents array

        Returns:
            The saved document
        """
        return await self._provider.save_full_document(document)

    async def get_llm_profiles(self) -> dict[str, Any]:
        """Return the document-level ``llmProfiles`` map."""
        document = await self._provider.get_full_document()
        return document.get("llmProfiles") or {}

    async def save_llm_profiles(self, profiles: dict[str, Any]) -> dict[str, Any]:
        """Replace the document-level ``llmProfiles`` map.

        Validates the prospective document before persisting so the
        controller layer is the single source of truth for 422
        responses. Raises :class:`AgentValidationError` when any
        agent step references an unknown profile id.
        """
        document = await self._provider.get_full_document()
        document["llmProfiles"] = profiles
        issues = validate_document(document)
        if issues:
            raise AgentValidationError("; ".join(issues), issues=issues)
        return await self._provider.save_full_document(document)

    async def get_tools(self) -> dict[str, Any]:
        """Return the document-level ``tools`` map."""
        document = await self._provider.get_full_document()
        return document.get("tools") or {}

    async def save_tools(self, tools: dict[str, Any]) -> dict[str, Any]:
        """Replace the document-level ``tools`` map.

        Validates the prospective document before persisting so the
        controller layer is the single source of truth for 422
        responses. Raises :class:`AgentValidationError` when any
        agent step references an unknown tool id.
        """
        document = await self._provider.get_full_document()
        document["tools"] = tools
        issues = validate_document(document)
        if issues:
            raise AgentValidationError("; ".join(issues), issues=issues)
        return await self._provider.save_full_document(document)

    async def get_agents(self) -> list[dict[str, Any]]:
        """Return the document-level ``agents`` list."""
        document = await self._provider.get_full_document()
        return document.get("agents") or []

    async def save_agents(self, agents: list[dict[str, Any]]) -> dict[str, Any]:
        """Replace the document-level ``agents`` list.

        Validates the prospective document before persisting so the
        controller layer is the single source of truth for 422
        responses. Raises :class:`AgentValidationError` when the
        prospective list doesn't pass validation.
        """
        document = await self._provider.get_full_document()
        document["agents"] = agents
        issues = validate_document(document)
        if issues:
            raise AgentValidationError("; ".join(issues), issues=issues)
        return await self._provider.save_full_document(document)

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