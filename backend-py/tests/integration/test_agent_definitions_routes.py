"""End-to-end tests for the per-section agent definitions routes.

The Python backend must expose the same per-section contract as the
.NET backend (phase 7): a whole-document route at
``/api/agent-definitions`` and three sub-routes for
``llm-profiles``, ``tools`` and ``agents``. PUTs must return 409
when a removed profile or tool id is still referenced by an agent
step, and 422 when the prospective document fails validation.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


def _write_document(directory: Path, document: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "agents.json").write_text(json.dumps(document, indent=2))


def _build_document(
    profiles: dict[str, Any] | None = None,
    tools: dict[str, Any] | None = None,
    agents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "llmProfiles": profiles or {},
        "tools": tools or {},
        "agents": agents or [],
    }


@pytest.fixture
def client() -> tuple[TestClient, Path]:
    """Spin up the FastAPI app against a temp configs directory.

    Patches ``get_settings`` to point at a fresh temp dir so each
    test starts with a known document and doesn't touch the user's
    checked-in ``configs/agents/agents.json``.
    """
    from unittest.mock import patch

    from src.api.routes import agent_definitions as routes_module
    from src.config import Settings, get_settings

    tmp = Path(tempfile.mkdtemp(prefix="agents-test-"))
    _write_document(tmp, _build_document())

    cached = get_settings()

    def _patched() -> Settings:
        s = cached.model_copy(deep=True) if hasattr(cached, "model_copy") else cached
        s.configs_path = tmp
        return s

    p = patch.object(routes_module, "get_settings", _patched)
    p.start()
    try:
        from src.main import app

        with TestClient(app) as test_client:
            yield test_client, tmp
    finally:
        p.stop()


def test_get_full_document_returns_migrated_shape(client) -> None:
    http, _ = client
    response = http.get("/api/agent-definitions")
    assert response.status_code == 200
    body = response.json()
    assert "llmProfiles" in body
    assert "tools" in body
    assert "agents" in body


def test_get_llm_profiles_returns_section(client) -> None:
    http, _ = client
    http.put(
        "/api/agent-definitions/llm-profiles",
        json={
            "azure-gpt5": {
                "provider": "azure-openai",
                "endpoint": "https://test.openai.azure.com/",
                "deployment": "gpt-5-mini",
                "apiKey": "test-key",
            }
        },
    )
    response = http.get("/api/agent-definitions/llm-profiles")
    assert response.status_code == 200
    assert "azure-gpt5" in response.json()


def test_get_tools_returns_section(client) -> None:
    http, _ = client
    http.put(
        "/api/agent-definitions/tools",
        json={
            "tavily-mcp": {
                "id": "tavily-mcp",
                "type": "mcp",
                "serverUrl": "https://example.com",
            }
        },
    )
    response = http.get("/api/agent-definitions/tools")
    assert response.status_code == 200
    assert "tavily-mcp" in response.json()


def test_get_agents_returns_section(client) -> None:
    http, _ = client
    http.put(
        "/api/agent-definitions/agents",
        json=[
            {
                "id": "translator",
                "steps": [],
            }
        ],
    )
    response = http.get("/api/agent-definitions/agents")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "translator"


def test_put_llm_profiles_validates_completeness(client) -> None:
    http, _ = client
    response = http.put(
        "/api/agent-definitions/llm-profiles",
        json={
            "broken": {
                "provider": "azure-openai",
                # Missing endpoint, deployment, apiKey.
            }
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "issues" in detail
    joined = " | ".join(detail["issues"])
    for expected in (
        "llmProfiles[broken].endpoint",
        "llmProfiles[broken].deployment",
        "llmProfiles[broken].apiKey",
    ):
        assert expected in joined, f"expected {expected!r} in issues, got {joined!r}"


def test_put_llm_profiles_cascade_delete_returns_409(client) -> None:
    """Removing a profile that is still referenced by an agent
    step must return 409 with the referencing steps listed."""
    http, tmp = client

    # Seed: profile that a step references, plus a step that
    # references it.
    document = _build_document(
        profiles={
            "azure-gpt5": {
                "provider": "azure-openai",
                "endpoint": "https://test.openai.azure.com/",
                "deployment": "gpt-5-mini",
                "apiKey": "test-key",
            }
        },
        agents=[
            {
                "id": "translator",
                "steps": [
                    {
                        "name": "chat",
                        "type": "agent",
                        "llmConfig": {"profileId": "azure-gpt5"},
                    }
                ],
            }
        ],
    )
    _write_document(tmp, document)

    # PUT that drops the profile (sends an empty map).
    response = http.put("/api/agent-definitions/llm-profiles", json={})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "azure-gpt5" in detail["message"]
    refs = detail["referencingSteps"]
    assert len(refs) == 1
    assert refs[0]["agentId"] == "translator"
    assert refs[0]["stepName"] == "chat"


def test_put_llm_profiles_unreferenced_profile_succeeds(client) -> None:
    http, _ = client
    response = http.put(
        "/api/agent-definitions/llm-profiles",
        json={
            "azure-gpt5": {
                "provider": "azure-openai",
                "endpoint": "https://test.openai.azure.com/",
                "deployment": "gpt-5-mini",
                "apiKey": "test-key",
            }
        },
    )
    assert response.status_code == 204


def test_put_tools_cascade_delete_returns_409(client) -> None:
    http, tmp = client

    document = _build_document(
        tools={
            "tavily-mcp": {
                "id": "tavily-mcp",
                "type": "mcp",
                "serverUrl": "https://example.com",
            }
        },
        agents=[
            {
                "id": "translator",
                "steps": [
                    {
                        "name": "search",
                        "type": "agent",
                        "tools": ["tavily-mcp"],
                    }
                ],
            }
        ],
    )
    _write_document(tmp, document)

    response = http.put("/api/agent-definitions/tools", json={})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "tavily-mcp" in detail["message"]
    refs = detail["referencingSteps"]
    assert len(refs) == 1
    assert refs[0]["agentId"] == "translator"
    assert refs[0]["stepName"] == "search"


def test_put_tools_unreferenced_tool_succeeds(client) -> None:
    http, _ = client
    response = http.put(
        "/api/agent-definitions/tools",
        json={
            "tavily-mcp": {
                "id": "tavily-mcp",
                "type": "mcp",
                "serverUrl": "https://example.com",
            }
        },
    )
    assert response.status_code == 204


def test_put_agents_validates_step_references(client) -> None:
    """PUT /api/agent-definitions/agents must reject agent steps
    that reference an unknown profile id, even if the profile is
    defined separately on the document."""
    http, tmp = client

    # Seed a document that has a profile but the agent step
    # references a non-existent one.
    document = _build_document(
        profiles={
            "azure-gpt5": {
                "provider": "azure-openai",
                "endpoint": "https://test.openai.azure.com/",
                "deployment": "gpt-5-mini",
                "apiKey": "test-key",
            }
        },
        agents=[],
    )
    _write_document(tmp, document)

    response = http.put(
        "/api/agent-definitions/agents",
        json=[
            {
                "id": "translator",
                "steps": [
                    {
                        "name": "chat",
                        "type": "agent",
                        "llmConfig": {"profileId": "nonexistent"},
                    }
                ],
            }
        ],
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(
        "nonexistent" in issue
        for issue in detail["issues"]
    )
