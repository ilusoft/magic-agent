"""Agent definitions CRUD endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.application.agents.schemas import AgentDefinition
from src.application.agents.service import AgentService
from src.application.agents.exceptions import AgentNotFoundError, AgentValidationError
from src.config import get_settings
from src.infrastructure.persistence.file_provider import FileAgentDefinitionsProvider

router = APIRouter()


def get_agent_service() -> AgentService:
    """Get agent service instance."""
    settings = get_settings()
    provider = FileAgentDefinitionsProvider(settings.configs_path)
    return AgentService(provider)


@router.get("/definitions")
async def list_agent_definitions() -> list[dict[str, Any]]:
    """List all agent definitions.

    Returns:
        List of agent definition dicts
    """
    service = get_agent_service()
    agents = await service.list_agents()
    return [a.model_dump() for a in agents]


@router.put("/definitions")
async def upsert_agent_definition(
    agent_id: str | None = None,
    definition: AgentDefinition | None = None,
) -> dict[str, Any]:
    """Create or update an agent definition.

    Args:
        agent_id: Optional agent ID (uses definition.name if not provided)
        definition: Agent definition

    Returns:
        The saved agent definition
    """
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Definition is required",
        )

    service = get_agent_service()
    agent_id = agent_id or definition.name

    try:
        result = await service.upsert_agent(agent_id, definition)
        return result.model_dump()
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    """Get a specific agent definition by ID.

    Args:
        agent_id: Agent identifier

    Returns:
        Agent definition
    """
    service = get_agent_service()

    try:
        result = await service.get_agent(agent_id)
        return result.model_dump()
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str) -> dict[str, str]:
    """Delete an agent definition.

    Args:
        agent_id: Agent identifier

    Returns:
        Confirmation message
    """
    service = get_agent_service()

    try:
        await service.delete_agent(agent_id)
        return {"message": f"Agent {agent_id} deleted"}
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )