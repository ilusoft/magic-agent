"""Unit tests for the diagnostics dataclasses.

Focused coverage for ``LLMCallConfig`` and the API-key fingerprint
helper. The end-to-end path through ``WorkflowExecutor`` is covered
in ``tests/agent_runtime/test_executor_stream_sink.py``.
"""

from __future__ import annotations

from src.application.agents.run_result import (
    AgentStepExecutionResult,
    LLMCallConfig,
    _fingerprint_api_key,
)


class TestFingerprintApiKey:
    """``_fingerprint_api_key`` is what keeps secrets out of the
    diagnostics endpoint while still letting operators tell
    "Azure key A" apart from "Azure key B".
    """

    def test_returns_none_for_empty(self) -> None:
        assert _fingerprint_api_key(None) is None
        assert _fingerprint_api_key("") is None

    def test_keeps_last_four_with_marker(self) -> None:
        assert _fingerprint_api_key("sk-abc12345") == "***2345"
        assert _fingerprint_api_key("real-key") == "***-key"

    def test_short_key_collapses_to_marker(self) -> None:
        # Anything <= 4 chars is too short to be safely truncated; the
        # helper must not echo the secret back.
        assert _fingerprint_api_key("ab") == "***"
        assert _fingerprint_api_key("abcd") == "***"


class TestLLMCallConfig:
    """Round-trip and shape checks for ``LLMCallConfig``."""

    def test_to_dict_uses_camel_case(self) -> None:
        cfg = LLMCallConfig(
            provider="openai-compatible",
            model="qwen-3.5",
            base_url="http://127.0.0.1:8000/v1",
            api_key_fingerprint="***abcd",
        )
        assert cfg.to_dict() == {
            "provider": "openai-compatible",
            "model": "qwen-3.5",
            "endpoint": None,
            "baseUrl": "http://127.0.0.1:8000/v1",
            "deployment": None,
            "apiVersion": None,
            "temperature": None,
            "maxTokens": None,
            "apiKeyFingerprint": "***abcd",
        }

    def test_from_dict_reads_snake_case(self) -> None:
        """``from_dict`` consumes the snake_case shape used by the
        dataclass field names; the camelCase ``to_dict`` is for the
        wire format. This matches the pre-existing pattern in
        ``AgentRunResult.from_dict`` / ``AgentStepExecutionResult.from_dict``.
        """
        restored = LLMCallConfig.from_dict(
            {
                "provider": "azure-openai",
                "model": "gpt-5-mini",
                "endpoint": "https://x.openai.azure.com/",
                "deployment": "gpt-5-mini",
                "api_version": "2024-12-01-preview",
                "temperature": 0.5,
                "max_tokens": 1024,
                "api_key_fingerprint": "***abcd",
            }
        )
        assert restored == LLMCallConfig(
            provider="azure-openai",
            model="gpt-5-mini",
            endpoint="https://x.openai.azure.com/",
            deployment="gpt-5-mini",
            api_version="2024-12-01-preview",
            temperature=0.5,
            max_tokens=1024,
            api_key_fingerprint="***abcd",
        )


class TestStepResultLLMConfig:
    """``AgentStepExecutionResult`` round-trips ``llm_config`` so the
    diagnostics endpoint can carry it through serialisation.
    """

    def test_defaults_to_none(self) -> None:
        step = AgentStepExecutionResult(name="x", type="setVariables", output="")
        assert step.llm_config is None

    def test_to_dict_includes_llm_config_when_set(self) -> None:
        step = AgentStepExecutionResult(
            name="chat",
            type="agent",
            output="hi",
            llm_config=LLMCallConfig(
                provider="openai-compatible",
                base_url="http://127.0.0.1:8000/v1",
                model="qwen-3.5",
            ),
        )
        assert step.to_dict()["llmConfig"] == {
            "provider": "openai-compatible",
            "model": "qwen-3.5",
            "endpoint": None,
            "baseUrl": "http://127.0.0.1:8000/v1",
            "deployment": None,
            "apiVersion": None,
            "temperature": None,
            "maxTokens": None,
            "apiKeyFingerprint": None,
        }

    def test_to_dict_omits_llm_config_when_none(self) -> None:
        step = AgentStepExecutionResult(name="x", type="setVariables", output="")
        assert step.to_dict()["llmConfig"] is None

    def test_from_dict_reads_snake_case_llm_config(self) -> None:
        restored = AgentStepExecutionResult.from_dict(
            {
                "name": "chat",
                "type": "agent",
                "output": "hi",
                "llm_config": {
                    "provider": "azure-openai",
                    "deployment": "d1",
                },
            }
        )
        assert restored.llm_config == LLMCallConfig(
            provider="azure-openai", deployment="d1"
        )
