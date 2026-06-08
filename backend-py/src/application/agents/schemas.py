"""Agent schemas using Pydantic."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str = Field(description="LLM provider (openai, azure-openai)")
    model: str = Field(description="Model name")
    api_key_secret: str | None = Field(default=None, description="API key secret name")
    endpoint: str | None = Field(default=None, description="Endpoint URL")
    deployment: str | None = Field(default=None, description="Deployment name")


class ToolDefinition(BaseModel):
    """Tool definition for an agent."""

    type: str = Field(description="Tool type (http, mcp)")
    name: str = Field(description="Tool name")
    description: str | None = Field(default=None, description="Tool description")
    base_url: str | None = Field(default=None, description="Base URL for HTTP tools")
    server_url: str | None = Field(default=None, description="MCP server URL")
    protocol: str | None = Field(default=None, description="MCP protocol (http, sse)")
    headers: dict[str, str] | None = Field(default=None, description="HTTP headers")
    allowed_tools: list[str] | None = Field(default=None, description="Allowed MCP tools")
    actions: list[dict[str, Any]] | None = Field(default=None, description="Tool actions")


class AgentStepDefinition(BaseModel):
    """Step definition within an agent workflow."""

    id: str = Field(description="Step ID")
    type: str = Field(description="Step type (input, chat, agent-step)")
    description: str | None = Field(default=None, description="Step description")
    agent: str | None = Field(default=None, description="Agent name for agent-step type")
    parameters: dict[str, Any] | None = Field(default=None, description="Step parameters")
    conversation: dict[str, Any] | None = Field(default=None, description="Conversation config")


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
    """Complete agent definition."""

    name: str = Field(description="Agent name")
    description: str | None = Field(default=None, description="Agent description")
    llm: LLMConfig | None = Field(default=None, description="LLM configuration")
    system_prompt: str | None = Field(default=None, description="System prompt")
    tools: list[ToolDefinition] = Field(default_factory=list)
    workflow: WorkflowDefinition | None = Field(default=None)
    runtime: RuntimeConfig | None = Field(default=None)
    default_parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}