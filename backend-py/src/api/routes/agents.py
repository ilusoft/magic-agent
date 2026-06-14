"""Agent definitions CRUD endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from starlette import status

from src.application.agents.exceptions import AgentNotFoundError
from src.application.agents.service import AgentService
from src.config import get_settings
from src.infrastructure.persistence.file_provider import FileAgentDefinitionsProvider

router = APIRouter()


def get_agent_service() -> AgentService:
    """Get agent service instance."""
    settings = get_settings()
    provider = FileAgentDefinitionsProvider(settings.configs_path)
    return AgentService(provider)


@router.get("/definitions")
async def get_agent_definitions_document() -> dict[str, Any]:
    """Get the full agent definitions document.

    Returns the entire contents of agents.json with all metadata
    (agents array, viewLayout, streaming config, etc.) preserved.

    Returns:
        Full agent definitions document
    """
    service = get_agent_service()
    return await service.get_full_document()


@router.put("/definitions")
async def save_agent_definitions_document(
    document: dict[str, Any],
) -> dict[str, Any]:
    """Save the full agent definitions document.

    Accepts the complete document structure (with agents array,
    viewLayout, streaming config, etc.) and writes it to agents.json.

    Args:
        document: Full agent definitions document

    Returns:
        The saved document
    """
    service = get_agent_service()
    return await service.save_full_document(document)


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