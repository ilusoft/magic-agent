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

ProviderName = Literal["openai", "azure-openai", "openai-compatible"]

_LOCAL_API_KEY_FALLBACK = "not-needed"


class LLMConfig(BaseModel):
    """Configuration for an LLM client."""

    provider: ProviderName
    model: str = "gpt-4o"
    api_key: str | None = None
    endpoint: str | None = None
    base_url: str | None = None
    deployment: str | None = None
    api_version: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None


class LLMFactory:
    """Factory for creating LLM chat model instances.

    Supports OpenAI, Azure OpenAI, and OpenAI-compatible providers
    (e.g. local servers such as vLLM, llama.cpp, Ollama's OpenAI shim,
    LM Studio, etc.).

    Model instances are cached based on their configuration to avoid
    re-instantiation when the same model is used across multiple
    workflow steps with identical settings.
    """

    _model_cache: dict[str, "BaseChatModel"] = {}

    def _make_cache_key(self, config: LLMConfig) -> str:
        """Generate a cache key from LLM config for model reuse.

        The cache key includes all configuration that affects the model
        instance, including the resolved api_key to ensure different
        credentials produce different cached models.
        """
        parts = [
            config.provider,
            config.model or "",
            config.endpoint or "",
            config.base_url or "",
            config.deployment or "",
            config.api_version or "",
            str(config.temperature),
            str(config.max_tokens or ""),
            config.api_key or "",
        ]
        return "|".join(parts)

    def create_chat_model(
        self,
        provider: ProviderName,
        model: str | None = None,
        api_key: str | None = None,
        endpoint: str | None = None,
        base_url: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> BaseChatModel:
        """Create a chat model instance.

        Args:
            provider: LLM provider (openai, azure-openai, openai-compatible)
            model: Model name
            api_key: API key (supports ${ENV_VAR} syntax)
            endpoint: Endpoint URL (for Azure)
            base_url: Base URL for OpenAI-compatible providers
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

        if base_url:
            base_url = resolve_env_vars(base_url)

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
            base_url=base_url or settings.llm_base_url,
            deployment=deployment or settings.llm_deployment,
            api_version=api_version or settings.llm_api_version,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        cache_key = self._make_cache_key(config)
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]

        model = self._create_model(config)
        self._model_cache[cache_key] = model
        return model

    def _create_model(self, config: LLMConfig) -> BaseChatModel:
        """Create model from config."""
        if config.provider == "azure-openai":
            return self._create_azure_openai(config)
        if config.provider == "openai":
            return self._create_openai(config)
        if config.provider == "openai-compatible":
            return self._create_openai_compatible(config)
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

    def _create_openai_compatible(self, config: LLMConfig) -> ChatOpenAI:
        """Create a chat model for an OpenAI-compatible endpoint.

        Targets local servers that expose ``/v1/chat/completions``
        (vLLM, llama.cpp, Ollama, LM Studio, etc.). The ``base_url``
        is required and points at the ``.../v1`` root of the server.
        Most local servers ignore the API key, so when one is not
        supplied we fall back to a harmless placeholder rather than
        hard-failing.

        When we end up using the placeholder we log a warning so the
        operator can tell from the logs why the call is about to
        return ``Invalid API key`` (some local servers — qwen
        built with an auth shim, gated vLLM, etc. — *do* validate
        the header and reject anything that isn't the real key).
        """
        if not config.base_url:
            raise ValueError(
                "OpenAI-compatible provider requires a base_url "
                "(e.g. http://127.0.0.1:8000/v1)."
            )

        api_key = config.api_key
        if not api_key:
            import structlog

            structlog.get_logger(__name__).warning(
                "openai_compatible_api_key_missing",
                base_url=config.base_url,
                model=config.model,
                hint=(
                    "No API key was resolved for the openai-compatible "
                    "provider; substituting 'not-needed'. If the local "
                    "server returns 401 'Invalid API key', set "
                    "OPENAI_API_KEY (or LLM_API_KEY) in the environment, "
                    "or add 'apiKey' to the agent's defaultParameters."
                ),
            )
            api_key = _LOCAL_API_KEY_FALLBACK

        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "base_url": config.base_url,
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