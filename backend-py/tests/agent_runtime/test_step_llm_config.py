"""Tests for per-step LLM config resolution.

Mirrors the .NET ``StepChatClientResolverTests``. The Python
executor resolves the LLM config per step from the document's
``llmProfiles`` map, merging any inline overrides on the step's
``llmConfig``. When no profile or inline config is present, the
legacy agent-level resolution is used.
"""

from __future__ import annotations

import pytest

from src.agent_runtime.workflow_executor import WorkflowExecutor


def _make_executor() -> WorkflowExecutor:
    return WorkflowExecutor()


def _base_document() -> dict:
    return {
        "llmProfiles": {
            "azure-gpt5": {
                "provider": "azure-openai",
                "endpoint": "https://test.openai.azure.com/",
                "deployment": "gpt-5-mini",
                "apiVersion": "2024-12-01-preview",
                "apiKey": "azure-key-1234",
            },
            "qwen-local": {
                "provider": "openai-compatible",
                "baseUrl": "http://127.0.0.1:8000/v1",
                "model": "Qwen-35B",
                "apiKey": "qwen-key-5678",
            },
        },
    }


class TestResolveStepLlmConfig:
    def setup_method(self) -> None:
        self.executor = _make_executor()

    def test_profile_id_resolves_to_azure_config(self) -> None:
        step = {"name": "chat", "llmConfig": {"profileId": "azure-gpt5"}}
        resolved = self.executor._resolve_step_llm_config(step, _base_document())
        assert resolved is not None
        assert resolved["provider"] == "azure-openai"
        assert resolved["endpoint"] == "https://test.openai.azure.com/"
        assert resolved["deployment"] == "gpt-5-mini"
        assert resolved["apiKey"] == "azure-key-1234"
        assert resolved["apiVersion"] == "2024-12-01-preview"

    def test_profile_id_resolves_to_openai_compatible_config(self) -> None:
        step = {"name": "chat", "llmConfig": {"profileId": "qwen-local"}}
        resolved = self.executor._resolve_step_llm_config(step, _base_document())
        assert resolved is not None
        assert resolved["provider"] == "openai-compatible"
        assert resolved["baseUrl"] == "http://127.0.0.1:8000/v1"
        assert resolved["model"] == "Qwen-35B"
        assert resolved["apiKey"] == "qwen-key-5678"

    def test_inline_overrides_profile_fields(self) -> None:
        step = {
            "name": "chat",
            "llmConfig": {
                "profileId": "azure-gpt5",
                "temperature": 0.2,
                "deployment": "gpt-5-mini-override",
            },
        }
        resolved = self.executor._resolve_step_llm_config(step, _base_document())
        assert resolved is not None
        assert resolved["deployment"] == "gpt-5-mini-override"
        assert resolved["temperature"] == 0.2
        assert resolved["endpoint"] == "https://test.openai.azure.com/"
        assert resolved["apiKey"] == "azure-key-1234"

    def test_inline_only_without_profile(self) -> None:
        step = {
            "name": "chat",
            "llmConfig": {
                "provider": "openai-compatible",
                "baseUrl": "http://localhost:9999/v1",
                "model": "Custom-Model",
                "apiKey": "inline-key-1234",
            },
        }
        resolved = self.executor._resolve_step_llm_config(step, _base_document())
        assert resolved is not None
        assert resolved["provider"] == "openai-compatible"
        assert resolved["baseUrl"] == "http://localhost:9999/v1"
        assert resolved["model"] == "Custom-Model"
        assert resolved["apiKey"] == "inline-key-1234"

    def test_missing_profile_id_falls_through_to_inline(self) -> None:
        step = {
            "name": "chat",
            "llmConfig": {
                "profileId": "nonexistent",
                "provider": "azure-openai",
                "endpoint": "https://fallback.openai.azure.com/",
                "deployment": "fallback-deployment",
                "apiKey": "fallback-key-1234",
            },
        }
        resolved = self.executor._resolve_step_llm_config(step, _base_document())
        assert resolved is not None
        assert resolved["endpoint"] == "https://fallback.openai.azure.com/"
        assert resolved["apiKey"] == "fallback-key-1234"

    def test_missing_profile_id_no_inline_returns_none(self) -> None:
        step = {"name": "chat", "llmConfig": {"profileId": "nonexistent"}}
        resolved = self.executor._resolve_step_llm_config(step, _base_document())
        assert resolved is None

    def test_no_llm_config_returns_none(self) -> None:
        step = {"name": "chat"}
        resolved = self.executor._resolve_step_llm_config(step, _base_document())
        assert resolved is None

    def test_no_document_returns_none(self) -> None:
        step = {"name": "chat", "llmConfig": {"profileId": "azure-gpt5"}}
        resolved = self.executor._resolve_step_llm_config(step, None)
        assert resolved is None

    def test_snake_case_profile_id_alias(self) -> None:
        step = {"name": "chat", "llmConfig": {"profile_id": "azure-gpt5"}}
        resolved = self.executor._resolve_step_llm_config(step, _base_document())
        assert resolved is not None
        assert resolved["provider"] == "azure-openai"

    def test_snake_case_document_profiles_alias(self) -> None:
        document = {"llm_profiles": _base_document()["llmProfiles"]}
        step = {"name": "chat", "llmConfig": {"profileId": "azure-gpt5"}}
        resolved = self.executor._resolve_step_llm_config(step, document)
        assert resolved is not None
        assert resolved["provider"] == "azure-openai"

    def test_inline_headers_override(self) -> None:
        step = {
            "name": "chat",
            "llmConfig": {
                "provider": "openai-compatible",
                "baseUrl": "http://localhost:9999/v1",
                "model": "Custom-Model",
                "apiKey": "inline-key-1234",
                "headers": {"X-Custom-Header": "custom-value"},
            },
        }
        resolved = self.executor._resolve_step_llm_config(step, _base_document())
        assert resolved is not None
        assert resolved["headers"] == {"X-Custom-Header": "custom-value"}


class TestResolveLlmConfigFallback:
    def setup_method(self) -> None:
        self.executor = _make_executor()

    def test_falls_back_to_legacy_agent_resolution_when_no_step_config(self) -> None:
        agent_definition = {
            "llm": {
                "provider": "azure-openai",
                "endpoint": "https://legacy.openai.azure.com/",
                "deployment": "legacy-deployment",
                "apiKey": "legacy-key-1234",
            }
        }
        step = {"name": "chat"}
        resolved = self.executor._resolve_llm_config(agent_definition, step=step, document=_base_document())
        assert resolved["provider"] == "azure-openai"
        assert resolved["endpoint"] == "https://legacy.openai.azure.com/"
        assert resolved["apiKey"] == "legacy-key-1234"

    def test_per_step_resolution_wins_over_legacy(self) -> None:
        agent_definition = {
            "llm": {
                "provider": "azure-openai",
                "endpoint": "https://legacy.openai.azure.com/",
                "deployment": "legacy-deployment",
                "apiKey": "legacy-key-1234",
            }
        }
        step = {"name": "chat", "llmConfig": {"profileId": "qwen-local"}}
        resolved = self.executor._resolve_llm_config(agent_definition, step=step, document=_base_document())
        assert resolved["provider"] == "openai-compatible"
        assert resolved["baseUrl"] == "http://127.0.0.1:8000/v1"
        assert resolved["model"] == "Qwen-35B"
        assert resolved["apiKey"] == "qwen-key-5678"

    def test_env_var_placeholder_in_api_key_is_resolved(self) -> None:
        import os

        os.environ["TEST_LLM_KEY"] = "env-var-key-1234"
        try:
            agent_definition = {
                "llm": {
                    "provider": "azure-openai",
                    "endpoint": "https://test.openai.azure.com/",
                    "deployment": "test-deployment",
                    "apiKey": "${TEST_LLM_KEY}",
                }
            }
            step = {"name": "chat"}
            resolved = self.executor._resolve_llm_config(agent_definition, step=step, document=None)
            assert resolved["api_key"] == "env-var-key-1234"
        finally:
            del os.environ["TEST_LLM_KEY"]


class TestBuildLlmCallConfig:
    def setup_method(self) -> None:
        self.executor = _make_executor()

    def test_per_step_azure_profile_emits_fingerprint(self) -> None:
        agent_definition = {}
        step = {"name": "chat", "llmConfig": {"profileId": "azure-gpt5"}}
        call_config = self.executor._build_llm_call_config(agent_definition, step=step, document=_base_document())
        assert call_config.provider == "azure-openai"
        assert call_config.endpoint == "https://test.openai.azure.com/"
        assert call_config.deployment == "gpt-5-mini"
        assert call_config.api_version == "2024-12-01-preview"
        assert call_config.api_key_fingerprint == "***1234"

    def test_per_step_qwen_profile_emits_fingerprint(self) -> None:
        agent_definition = {}
        step = {"name": "chat", "llmConfig": {"profileId": "qwen-local"}}
        call_config = self.executor._build_llm_call_config(agent_definition, step=step, document=_base_document())
        assert call_config.provider == "openai-compatible"
        assert call_config.base_url == "http://127.0.0.1:8000/v1"
        assert call_config.model == "Qwen-35B"
        assert call_config.api_key_fingerprint == "***5678"
        assert call_config.deployment is None
        assert call_config.endpoint is None

    def test_legacy_resolution_unchanged(self) -> None:
        agent_definition = {
            "llm": {
                "provider": "azure-openai",
                "endpoint": "https://legacy.openai.azure.com/",
                "deployment": "legacy-deployment",
                "apiKey": "legacy-key-1234",
            }
        }
        call_config = self.executor._build_llm_call_config(agent_definition)
        assert call_config.provider == "azure-openai"
        assert call_config.endpoint == "https://legacy.openai.azure.com/"
        assert call_config.deployment == "legacy-deployment"
        assert call_config.api_key_fingerprint == "***1234"
