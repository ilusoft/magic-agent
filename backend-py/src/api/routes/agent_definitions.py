"""Per-section agent definitions endpoints.

Mirrors the .NET ``LlmProfilesController`` / ``ToolsController`` /
``AgentsController`` introduced in phase 7:

  * ``GET /api/agent-definitions`` / ``PUT /api/agent-definitions`` —
    whole-document read/write at the new route (the old
    ``/api/agents/definitions`` route is still served by
    ``agents.py`` for backward compatibility).
  * ``GET/PUT /api/agent-definitions/llm-profiles`` — replace the
    document-level ``llmProfiles`` map. 409 on cascade-delete.
  * ``GET/PUT /api/agent-definitions/tools`` — replace the
    document-level ``tools`` map. 409 on cascade-delete.
  * ``GET/PUT /api/agent-definitions/agents`` — replace the
    document-level ``agents`` list.

Cascade-delete protection: a PUT that removes a profile or tool id
that is still referenced by one or more agent steps returns 409
with the list of referencing steps. No auto-rewire, no soft-delete.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from src.application.agents.exceptions import AgentValidationError
from src.application.agents.service import AgentService
from src.application.agents.validator import validate_document
from src.config import get_settings
from src.infrastructure.persistence.file_provider import FileAgentDefinitionsProvider

router = APIRouter()


def _get_service() -> AgentService:
    settings = get_settings()
    provider = FileAgentDefinitionsProvider(settings.configs_path)
    return AgentService(provider)


def _find_referencing_llm_profiles(
    document: dict[str, Any], removed_ids: set[str]
) -> list[dict[str, str]]:
    """Return ``[{"agentId": ..., "stepName": ...}, ...]`` for every
    step that still references a removed profile id."""
    references: list[dict[str, str]] = []
    for agent in document.get("agents") or []:
        if not agent:
            continue
        agent_id = agent.get("id", "")
        for step in agent.get("steps") or []:
            if not step:
                continue
            profile_id = (step.get("llmConfig") or {}).get("profileId")
            if not profile_id:
                continue
            if profile_id in removed_ids:
                references.append(
                    {"agentId": agent_id, "stepName": step.get("name", "")}
                )
    return references


def _find_referencing_tools(
    document: dict[str, Any], removed_ids: set[str]
) -> list[dict[str, str]]:
    """Return ``[{"agentId": ..., "stepName": ...}, ...]`` for every
    step that still references a removed tool id."""
    references: list[dict[str, str]] = []
    for agent in document.get("agents") or []:
        if not agent:
            continue
        agent_id = agent.get("id", "")
        for step in agent.get("steps") or []:
            if not step:
                continue
            step_name = step.get("name", "")
            for tool_id in step.get("tools") or []:
                if tool_id in removed_ids:
                    references.append(
                        {"agentId": agent_id, "stepName": step_name}
                    )
                    break
    return references


@router.get("")
async def get_full_document() -> dict[str, Any]:
    """Return the full agent definitions document at the new route."""
    service = _get_service()
    return await service.get_full_document()


@router.put("")
async def put_full_document(document: dict[str, Any]) -> dict[str, Any]:
    """Replace the full agent definitions document."""
    service = _get_service()
    issues = validate_document(document)
    if issues:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Validation failed", "issues": issues},
        )
    return await service.save_full_document(document)


@router.get("/llm-profiles")
async def get_llm_profiles() -> dict[str, Any]:
    """Return the document-level LLM profiles map."""
    service = _get_service()
    return await service.get_llm_profiles()


@router.put("/llm-profiles")
async def put_llm_profiles(
    profiles: dict[str, Any],
) -> Response:
    """Replace the document-level LLM profiles map.

    Returns 409 if any of the removed profile ids are still
    referenced by an agent step.
    """
    service = _get_service()
    document = await service.get_full_document()
    removed = set((document.get("llmProfiles") or {}).keys()) - set(
        profiles.keys()
    )
    if removed:
        references = _find_referencing_llm_profiles(document, removed)
        if references:
            removed_list = ", ".join(sorted(removed))
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": (
                        f"LLM profile(s) '{removed_list}' "
                        "cannot be removed: still referenced by "
                        f"{len(references)} step(s)."
                    ),
                    "referencingSteps": references,
                },
            )
    try:
        await service.save_llm_profiles(profiles)
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_validation_detail(e),
        ) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tools")
async def get_tools() -> dict[str, Any]:
    """Return the document-level tools map."""
    service = _get_service()
    return await service.get_tools()


@router.put("/tools")
async def put_tools(
    tools: dict[str, Any],
) -> Response:
    """Replace the document-level tools map.

    Returns 409 if any of the removed tool ids are still referenced
    by an agent step.
    """
    service = _get_service()
    document = await service.get_full_document()
    removed = set((document.get("tools") or {}).keys()) - set(tools.keys())
    if removed:
        references = _find_referencing_tools(document, removed)
        if references:
            removed_list = ", ".join(sorted(removed))
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": (
                        f"Tool(s) '{removed_list}' "
                        "cannot be removed: still referenced by "
                        f"{len(references)} step(s)."
                    ),
                    "referencingSteps": references,
                },
            )
    try:
        await service.save_tools(tools)
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_validation_detail(e),
        ) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/agents")
async def get_agents() -> list[dict[str, Any]]:
    """Return the document-level agents list."""
    service = _get_service()
    return await service.get_agents()


@router.put("/agents")
async def put_agents(
    agents: list[dict[str, Any]],
) -> Response:
    """Replace the document-level agents list."""
    service = _get_service()
    try:
        await service.save_agents(agents)
    except AgentValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_validation_detail(e),
        ) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _validation_detail(error: AgentValidationError) -> dict[str, Any]:
    """Build a 422 response body from an ``AgentValidationError``.

    Exposes the full issues list (when present) so the UI can show
    every problem at once instead of one at a time.
    """
    issues = getattr(error, "issues", None) or [str(error)]
    return {"message": "; ".join(issues) if issues else str(error), "issues": issues}
