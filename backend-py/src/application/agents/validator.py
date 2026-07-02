"""Document-level validation for the post-refactor ``agents.json`` shape.

Mirrors the .NET ``AgentDefinitionsDocumentValidator``:

  - Every ``step.llmConfig.profileId`` resolves to a key in
    ``document.llmProfiles``.
  - Every ``step.tools[i]`` resolves to a key in ``document.tools``.
  - Every profile has the required fields for its declared
    ``provider`` and a non-empty ``apiKey`` (literal or ``${ENV_VAR}``).

Returns a list of human-readable issue strings. Empty list means the
document is valid.
"""

from __future__ import annotations

import re
from typing import Any


_REQUIRED_AZURE_FIELDS = ("endpoint", "deployment")
_REQUIRED_OPENAI_COMPATIBLE_FIELDS = ("baseUrl", "model")
_ENV_VAR_PATTERN = re.compile(r"^\$\{[^}]+\}$")


def _is_valid_api_key(value: Any) -> bool:
    if not value or not isinstance(value, str):
        return False
    return bool(value.strip())


def validate_document(document: dict[str, Any]) -> list[str]:
    """Validate the post-refactor ``agents.json`` shape.

    Returns a list of issue strings (empty when the document is
    valid). The list is flat — the caller is responsible for
    surfacing it as a 422 response or similar.
    """
    issues: list[str] = []

    profiles = document.get("llmProfiles") or {}
    tools = document.get("tools") or {}

    for profile_id, profile in profiles.items():
        provider = (profile or {}).get("provider")
        if not provider:
            issues.append(
                f"llmProfiles[{profile_id}].provider is required"
            )
            continue

        if provider == "azure-openai":
            for field in _REQUIRED_AZURE_FIELDS:
                if not (profile or {}).get(field):
                    issues.append(
                        f"llmProfiles[{profile_id}].{field} is required for provider 'azure-openai'"
                    )
        elif provider == "openai-compatible":
            for field in _REQUIRED_OPENAI_COMPATIBLE_FIELDS:
                if not (profile or {}).get(field):
                    issues.append(
                        f"llmProfiles[{profile_id}].{field} is required for provider 'openai-compatible'"
                    )
        else:
            issues.append(
                f"llmProfiles[{profile_id}].provider '{provider}' is not recognized"
            )

        if not _is_valid_api_key((profile or {}).get("apiKey")):
            issues.append(
                f"llmProfiles[{profile_id}].apiKey is required"
            )

    for agent_idx, agent in enumerate(document.get("agents") or []):
        if not agent:
            continue
        agent_id = agent.get("id", f"<index {agent_idx}>")
        for step_idx, step in enumerate(agent.get("steps") or []):
            if not step:
                continue
            step_name = step.get("name", f"<index {step_idx}>")
            llm_config = step.get("llmConfig") or {}
            profile_id = llm_config.get("profileId")
            if profile_id and profile_id not in profiles:
                issues.append(
                    f"agents[{agent_id}].steps[{step_name}].llmConfig.profileId "
                    f"references unknown profile '{profile_id}'"
                )
            for tool_idx, tool_id in enumerate(step.get("tools") or []):
                if not tool_id:
                    continue
                if tool_id not in tools:
                    issues.append(
                        f"agents[{agent_id}].steps[{step_name}].tools[{tool_idx}] "
                        f"references unknown tool '{tool_id}'"
                    )

    return issues
