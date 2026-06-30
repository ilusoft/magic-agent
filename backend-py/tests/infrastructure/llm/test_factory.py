"""Tests for the LLM client factory."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.infrastructure.llm.factory import LLMConfig, LLMFactory


class TestLLMConfig:
    """Pydantic model sanity checks."""

    def test_minimal_config(self) -> None:
        config = LLMConfig(provider="azure-openai")
        assert config.provider == "azure-openai"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.7
        assert config.api_version is None
        assert config.max_tokens is None

    def test_full_config(self) -> None:
        config = LLMConfig(
            provider="azure-openai",
            model="gpt-5-mini",
            api_key="k",
            endpoint="https://x.openai.azure.com/",
            deployment="gpt-5-mini",
            api_version="2024-08-01-preview",
            temperature=1.0,
            max_tokens=2048,
        )
        assert config.api_version == "2024-08-01-preview"
        assert config.max_tokens == 2048

    def test_invalid_provider_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LLMConfig(provider="not-a-provider")  # type: ignore[arg-type]


class TestCreateChatModel:
    """Tests for ``LLMFactory.create_chat_model`` resolution order."""

    def test_explicit_args_win_over_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Caller-supplied args (which originate from the agent JSON)
        must override any value sourced from ``Settings``/``.env``.
        """
        from src import config as config_module
        from src.infrastructure.llm import factory as factory_module

        class _FakeSettings:
            llm_api_key = "settings-key"
            llm_endpoint = "https://settings.openai.azure.com/"
            llm_base_url = "http://settings-host:1234/v1"
            llm_deployment = "settings-deployment"
            llm_model = "settings-model"
            llm_api_version = "settings-version"

        # The factory imports ``get_settings`` at module load, so we must
        # patch the symbol on the factory module itself (not just the
        # ``src.config`` namespace).
        monkeypatch.setattr(
            config_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.setattr(
            factory_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        factory = LLMFactory()
        llm = factory.create_chat_model(
            provider="azure-openai",
            api_key="agent-key",
            endpoint="https://agent.openai.azure.com/",
            deployment="agent-deployment",
            model="agent-model",
            api_version="agent-version",
        )

        # ``AzureChatOpenAI`` stores these on the underlying client.
        # Validate that the explicit values were used, not the
        # settings fallbacks.
        assert llm.azure_endpoint == "https://agent.openai.azure.com/"
        assert llm.openai_api_key.get_secret_value() == "agent-key"  # type: ignore[attr-defined]
        assert llm.deployment_name == "agent-deployment"  # type: ignore[attr-defined]
        assert llm.openai_api_version == "agent-version"  # type: ignore[attr-defined]
        assert llm.temperature == 0.7  # default preserved

    def test_settings_filled_when_caller_omits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the agent JSON doesn't carry a field, the factory must
        fall back to ``Settings`` (which reads from ``.env``) before
        defaulting.

        Regression: the factory used to ignore ``Settings`` entirely
        and only fell back to ``OPENAI_API_KEY``, which meant
        ``.env``-defined credentials never reached the LLM client.
        """
        from src import config as config_module
        from src.infrastructure.llm import factory as factory_module

        class _FakeSettings:
            llm_api_key = "settings-key"
            llm_endpoint = "https://settings.openai.azure.com/"
            llm_base_url = "http://settings-host:1234/v1"
            llm_deployment = "settings-deployment"
            llm_model = "settings-model"
            llm_api_version = "settings-version"

        monkeypatch.setattr(
            config_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.setattr(
            factory_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        factory = LLMFactory()
        llm = factory.create_chat_model(provider="azure-openai")

        assert llm.azure_endpoint == "https://settings.openai.azure.com/"
        assert llm.openai_api_key.get_secret_value() == "settings-key"  # type: ignore[attr-defined]
        assert llm.deployment_name == "settings-deployment"  # type: ignore[attr-defined]

    def test_env_placeholder_in_api_key_is_resolved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``apiKey`` values like ``{LLM_API_KEY}`` must resolve to the
        settings value before reaching ``AzureChatOpenAI``.

        Regression: pydantic-settings loads ``.env`` into the Settings
        object but not into ``os.environ``, so the original env-var
        resolver left ``{LLM_API_KEY}`` as a literal and the LLM
        client was constructed with ``api_key="{LLM_API_KEY}"``.
        """
        from src import config as config_module
        from src.infrastructure.llm import factory as factory_module

        class _FakeSettings:
            llm_api_key = "real-key"
            llm_endpoint = "https://x.openai.azure.com/"
            llm_base_url = None
            llm_deployment = "gpt-5-mini"
            llm_model = "gpt-5-mini"
            llm_api_version = "2024-08-01-preview"

        monkeypatch.setattr(
            config_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.setattr(
            factory_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        factory = LLMFactory()
        llm = factory.create_chat_model(
            provider="azure-openai",
            api_key="{LLM_API_KEY}",
        )
        assert llm.openai_api_key.get_secret_value() == "real-key"  # type: ignore[attr-defined]

    def test_azure_requires_endpoint_and_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import config as config_module
        from src.infrastructure.llm import factory as factory_module

        class _FakeSettings:
            llm_api_key = None
            llm_endpoint = None
            llm_base_url = None
            llm_deployment = "gpt-5-mini"
            llm_model = "gpt-5-mini"
            llm_api_version = "2024-08-01-preview"

        monkeypatch.setattr(
            config_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.setattr(
            factory_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        factory = LLMFactory()
        with pytest.raises(ValueError, match="endpoint is required"):
            factory.create_chat_model(provider="azure-openai")


class TestOpenAICompatibleProvider:
    """Tests for the ``openai-compatible`` provider (local LLM servers)."""

    def test_base_url_and_explicit_args_win(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import config as config_module
        from src.infrastructure.llm import factory as factory_module

        class _FakeSettings:
            llm_api_key = None
            llm_base_url = "http://settings-host:1234/v1"
            llm_model = "settings-model"
            llm_endpoint = None
            llm_deployment = None
            llm_api_version = None

        monkeypatch.setattr(
            config_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.setattr(
            factory_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        factory = LLMFactory()
        llm = factory.create_chat_model(
            provider="openai-compatible",
            model="qwen-3.6",
            base_url="http://127.0.0.1:8000/v1",
        )

        # ChatOpenAI exposes the base URL through ``openai_api_base``.
        assert llm.openai_api_base == "http://127.0.0.1:8000/v1"  # type: ignore[attr-defined]
        assert llm.model_name == "qwen-3.6"  # type: ignore[attr-defined]
        # No key supplied → fallback placeholder so local servers that
        # validate presence (but not value) still work.
        assert llm.openai_api_key.get_secret_value() == "not-needed"  # type: ignore[attr-defined]

    def test_settings_base_url_is_used_when_caller_omits(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import config as config_module
        from src.infrastructure.llm import factory as factory_module

        class _FakeSettings:
            llm_api_key = None
            llm_base_url = "http://127.0.0.1:8000/v1"
            llm_model = "qwen-3.6"
            llm_endpoint = None
            llm_deployment = None
            llm_api_version = None

        monkeypatch.setattr(
            config_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.setattr(
            factory_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        factory = LLMFactory()
        llm = factory.create_chat_model(provider="openai-compatible")

        assert llm.openai_api_base == "http://127.0.0.1:8000/v1"  # type: ignore[attr-defined]
        assert llm.model_name == "qwen-3.6"  # type: ignore[attr-defined]

    def test_explicit_api_key_overrides_placeholder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import config as config_module
        from src.infrastructure.llm import factory as factory_module

        class _FakeSettings:
            llm_api_key = None
            llm_base_url = "http://127.0.0.1:8000/v1"
            llm_model = "qwen-3.6"
            llm_endpoint = None
            llm_deployment = None
            llm_api_version = None

        monkeypatch.setattr(
            config_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.setattr(
            factory_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        factory = LLMFactory()
        llm = factory.create_chat_model(
            provider="openai-compatible",
            api_key="local-secret",
        )
        assert llm.openai_api_key.get_secret_value() == "local-secret"  # type: ignore[attr-defined]

    def test_requires_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import config as config_module
        from src.infrastructure.llm import factory as factory_module

        class _FakeSettings:
            llm_api_key = None
            llm_base_url = None
            llm_model = "qwen-3.6"
            llm_endpoint = None
            llm_deployment = None
            llm_api_version = None

        monkeypatch.setattr(
            config_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.setattr(
            factory_module, "get_settings", lambda: _FakeSettings()
        )
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        factory = LLMFactory()
        with pytest.raises(ValueError, match="requires a base_url"):
            factory.create_chat_model(provider="openai-compatible")
