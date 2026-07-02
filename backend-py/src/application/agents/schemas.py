"""Agent schemas using Pydantic.

These models document the canonical shape of ``agents.json`` and are
used by the per-step LLM resolution logic. The workflow executor itself
operates on raw dicts (not these Pydantic models) so it can stay
schema-agnostic, but the types live here for reference and for
upcoming validation work.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LLMProfileDefinition(BaseModel):
    """A named, reusable LLM configuration.

    Profiles are defined once at the document root and referenced by
    agent steps via ``StepLlmConfig.profileId``. A step can also
    override any subset of the profile's fields inline.
    """

    provider: str = Field(description="LLM provider (azure-openai, openai-compatible)")
    endpoint: str | None = Field(default=None, description="Azure OpenAI endpoint URL")
    deployment: str | None = Field(default=None, description="Azure OpenAI deployment name")
    api_version: str | None = Field(default=None, description="Azure OpenAI API version")
    base_url: str | None = Field(default=None, description="OpenAI-compatible base URL")
    model: str | None = Field(default=None, description="Model name (openai-compatible)")
    api_key: str | None = Field(default=None, description="API key or ${ENV_VAR} placeholder")
    headers: dict[str, str] | None = Field(default=None, description="Extra HTTP headers")
    temperature: float | None = Field(default=None, description="Default sampling temperature")
    max_tokens: int | None = Field(default=None, description="Default max output tokens")


class StepLlmConfig(BaseModel):
    """Per-step LLM override.

    Either a ``profileId`` reference (resolved against the document's
    ``llm_profiles`` map), an inline override, or both (profile + inline).
    Inline fields win when both are set.
    """

    profile_id: str | None = Field(default=None, description="Reference to a document-level LLM profile")
    provider: str | None = Field(default=None, description="Inline provider override")
    endpoint: str | None = Field(default=None, description="Inline Azure OpenAI endpoint override")
    deployment: str | None = Field(default=None, description="Inline Azure OpenAI deployment override")
    api_version: str | None = Field(default=None, description="Inline Azure OpenAI API version override")
    base_url: str | None = Field(default=None, description="Inline openai-compatible base URL override")
    model: str | None = Field(default=None, description="Inline model name override")
    api_key: str | None = Field(default=None, description="Inline API key override")
    headers: dict[str, str] | None = Field(default=None, description="Inline headers override")
    temperature: float | None = Field(default=None, description="Inline temperature override")
    max_tokens: int | None = Field(default=None, description="Inline max tokens override")


class ToolDefinition(BaseModel):
    """A globally-defined tool that an agent step can reference by id."""

    id: str = Field(description="Unique tool id (used as the reference key)")
    type: str = Field(description="Tool type (mcp, mcp-http)")
    name: str | None = Field(default=None, description="Display name")
    description: str | None = Field(default=None, description="Tool description")
    server_url: str | None = Field(default=None, description="MCP server URL")
    protocol: str | None = Field(default="auto", description="MCP transport protocol")
    headers: dict[str, str] | None = Field(default=None, description="HTTP headers")
    allowed_tools: list[str] | None = Field(default=None, description="Allowed MCP tool names")
    actions: list[dict[str, Any]] | None = Field(default=None, description="Tool aliases")
    forward_authorization_header: bool | None = Field(default=None)
    authorization_header_name: str | None = Field(default="Authorization")
    stop_on_tool_init_error: bool | None = Field(default=None)


class AgentStepDefinition(BaseModel):
    """A step inside an agent workflow.

    ``llm_config`` is the new per-step LLM override; when set it
    takes precedence over any workflow-level LLM config.
    """

    id: str | None = Field(default=None, description="Step ID (legacy)")
    name: str | None = Field(default=None, description="Step name")
    type: str = Field(description="Step type (agent, setVariables, echo, resetConversation)")
    description: str | None = Field(default=None)
    agent: str | None = Field(default=None, description="Legacy: agent name for agent-step type")
    parameters: dict[str, Any] | None = Field(default=None)
    variable_types: dict[str, str] | None = Field(default=None)
    provider: str | None = Field(default=None, description="Legacy per-step provider (deprecated)")
    options: dict[str, Any] | None = Field(default=None, description="Legacy per-step options (deprecated)")
    conversation: dict[str, Any] | None = Field(default=None)
    tools: list[str] | None = Field(default=None, description="References to document.tools ids")
    stop_on_tool_error: bool | None = Field(default=None)
    input_source: str | None = Field(default=None)
    outcomes: list[dict[str, Any]] | None = Field(default=None)
    is_start_step: bool | None = Field(default=None)
    llm_config: StepLlmConfig | None = Field(default=None, description="Per-step LLM override")


class WorkflowDefinition(BaseModel):
    """Workflow definition for an agent."""

    steps: list[AgentStepDefinition] = Field(default_factory=list)
    outputs: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeConfig(BaseModel):
    """Runtime configuration for agent execution."""

    max_iterations: int = Field(default=50)
    timeout_seconds: int = Field(default=120)
    retry_policy: dict[str, Any] | None = Field(default=None)


class AgentDefinition(BaseModel):
    """Complete agent definition.

    The old single-LLM ``llm`` block has been removed; LLM config
    now lives in the document-level ``llm_profiles`` map and is
    referenced per-step via ``AgentStepDefinition.llm_config``.
    """

    id: str = Field(description="Agent id (unique within the document)")
    name: str = Field(description="Agent name")
    description: str | None = Field(default=None)
    default_parameters: dict[str, Any] = Field(default_factory=dict)
    steps: list[AgentStepDefinition] = Field(default_factory=list)
    tools: list[str] | None = Field(default=None, description="Legacy: per-agent tool ids (deprecated)")
    view_layout: dict[str, Any] | None = Field(default=None, alias="viewLayout")
    streaming: dict[str, Any] | None = Field(default=None)

    model_config = {"extra": "allow", "populate_by_name": True}


class AgentDefinitionsDocument(BaseModel):
    """The top-level shape of ``agents.json``.

    Three sections: reusable LLM profiles, the global tool pool, and
    the list of agent workflows. The document is the single source of
    truth for both backends.
    """

    llm_profiles: dict[str, LLMProfileDefinition] = Field(default_factory=dict)
    tools: dict[str, ToolDefinition] = Field(default_factory=dict)
    agents: list[AgentDefinition] = Field(default_factory=list)

    model_config = {"extra": "allow"}