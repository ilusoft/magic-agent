"""LLM client factory for creating chat models."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal

from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import BaseModel

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from src.config import get_settings
from src.lib.security import resolve_env_vars


class LLMConfig(BaseModel):
    """Configuration for an LLM client."""

    provider: Literal["openai", "azure-openai"]
    model: str = "gpt-4o"
    api_key: str | None = None
    endpoint: str | None = None
    deployment: str | None = None
    api_version: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None


class LLMFactory:
    """Factory for creating LLM chat model instances.

    Supports OpenAI and Azure OpenAI providers.
    """

    def create_chat_model(
        self,
        provider: Literal["openai", "azure-openai"],
        model: str | None = None,
        api_key: str | None = None,
        endpoint: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> BaseChatModel:
        """Create a chat model instance.

        Args:
            provider: LLM provider (openai, azure-openai)
            model: Model name
            api_key: API key (supports ${ENV_VAR} syntax)
            endpoint: Endpoint URL (for Azure)
            deployment: Deployment name (for Azure)
            api_version: Azure OpenAI API version
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Configured chat model instance
        """
        # Resolve environment variables
        if api_key:
            api_key = resolve_env_vars(api_key)

        if endpoint:
            endpoint = resolve_env_vars(endpoint)

        if api_version:
            api_version = resolve_env_vars(api_version)

        settings = get_settings()

        config = LLMConfig(
            provider=provider,
            model=model or settings.llm_model,
            api_key=(
                api_key
                or settings.llm_api_key
                or os.environ.get("OPENAI_API_KEY")
            ),
            endpoint=endpoint or settings.llm_endpoint,
            deployment=deployment or settings.llm_deployment,
            api_version=api_version or settings.llm_api_version,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return self._create_model(config)

    def _create_model(self, config: LLMConfig) -> BaseChatModel:
        """Create model from config."""
        if config.provider == "azure-openai":
            return self._create_azure_openai(config)
        elif config.provider == "openai":
            return self._create_openai(config)
        else:
            raise ValueError(f"Unknown LLM provider: {config.provider}")

    def _create_azure_openai(self, config: LLMConfig) -> AzureChatOpenAI:
        """Create Azure OpenAI chat model."""
        if not config.endpoint:
            raise ValueError("Azure OpenAI endpoint is required")

        if not config.api_key:
            raise ValueError("Azure OpenAI API key is required")

        kwargs: dict[str, Any] = {
            "azure_endpoint": config.endpoint,
            "api_key": config.api_key,
            "temperature": config.temperature,
        }

        if config.deployment:
            kwargs["azure_deployment"] = config.deployment

        if config.api_version:
            kwargs["api_version"] = config.api_version

        if config.max_tokens:
            kwargs["max_tokens"] = config.max_tokens

        return AzureChatOpenAI(**kwargs)

    def _create_openai(self, config: LLMConfig) -> ChatOpenAI:
        """Create OpenAI chat model."""
        if not config.api_key:
            raise ValueError("OpenAI API key is required")

        kwargs: dict[str, Any] = {
            "api_key": config.api_key,
            "model": config.model,
            "temperature": config.temperature,
        }

        if config.max_tokens:
            kwargs["max_tokens"] = config.max_tokens

        return ChatOpenAI(**kwargs)


# Singleton instance
_llm_factory: LLMFactory | None = None


def get_llm_factory() -> LLMFactory:
    """Get the LLM factory singleton."""
    global _llm_factory
    if _llm_factory is None:
        _llm_factory = LLMFactory()
    return _llm_factory