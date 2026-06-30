"""Application configuration using Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=CONFIG_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Runtime
    configs_path: Path = Field(
        default=CONFIG_DIR.parent / "configs" / "agents",
        description="Path to agent/workflow JSON definitions",
    )

    # LLM Defaults
    llm_provider: Literal["openai", "azure-openai", "openai-compatible"] = Field(
        default="azure-openai",
        description="LLM provider to use",
    )
    llm_endpoint: str | None = Field(
        default=None,
        description="Azure OpenAI endpoint URL",
    )
    llm_base_url: str | None = Field(
        default=None,
        description=(
            "Base URL for OpenAI-compatible providers "
            "(e.g. http://127.0.0.1:8000/v1 for a local LLM server)."
        ),
    )
    llm_api_key: str | None = Field(
        default=None,
        description="API key for LLM provider",
    )
    llm_deployment: str = Field(
        default="gpt-4o",
        description="Model deployment name",
    )
    llm_model: str = Field(
        default="gpt-4o",
        description="Model name",
    )
    llm_api_version: str | None = Field(
        default=None,
        description="Azure OpenAI API version (e.g. 2024-08-01-preview)",
    )

    # API
    cors_origins: list[str] = Field(
        default=["http://localhost:5173"],
        description="CORS allowed origins",
    )
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Runtime Limits
    max_iterations: int = Field(
        default=50,
        description="Maximum agent execution iterations",
    )
    default_timeout_seconds: int = Field(
        default=120,
        description="Default agent run timeout",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()