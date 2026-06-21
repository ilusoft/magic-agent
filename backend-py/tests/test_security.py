"""Tests for environment variable resolution in agent definitions."""

from __future__ import annotations

import pytest

from src.lib.security import resolve_env_vars, resolve_value


class TestResolveEnvVars:
    """Tests for ``${ENV}`` / ``{ENV}`` placeholder substitution."""

    def test_dollar_brace_syntax(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_TEST_KEY", "secret-value")
        assert resolve_env_vars("${MY_TEST_KEY}") == "secret-value"

    def test_single_brace_syntax(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_TEST_KEY", "secret-value")
        assert resolve_env_vars("{MY_TEST_KEY}") == "secret-value"

    def test_unresolved_placeholder_is_preserved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MISSING_KEY_XYZ", raising=False)
        # No exception, no mutation - the literal stays for diagnostics.
        assert resolve_env_vars("${MISSING_KEY_XYZ}") == "${MISSING_KEY_XYZ}"

    def test_partial_substitution_in_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOST", "example.com")
        assert (
            resolve_env_vars("https://${HOST}/api")
            == "https://example.com/api"
        )

    def test_falls_back_to_settings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: the resolver used to look up ``os.environ`` only.
        pydantic-settings loads ``.env`` into the ``Settings`` object
        but does not put the values into ``os.environ``, so any
        ``${LLM_API_KEY}`` placeholder resolved to the literal
        ``${LLM_API_KEY}`` and broke LLM instantiation.

        The resolver must consult ``Settings`` as a fallback.
        """
        from src import config as config_module

        class _FakeSettings:
            llm_api_key = "settings-key-value"

        # The lookup function does ``from src.config import get_settings``
        # inside the function body, so patching ``src.config.get_settings``
        # is enough.
        monkeypatch.setattr(
            config_module, "get_settings", lambda: _FakeSettings()
        )
        # Ensure the env var is *not* set so we actually exercise the
        # Settings fallback.
        monkeypatch.delenv("LLM_API_KEY", raising=False)

        assert (
            resolve_env_vars("{LLM_API_KEY}") == "settings-key-value"
        )


class TestResolveValue:
    """Recursive resolver used when loading agent JSON files."""

    def test_dict_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("K", "v")
        result = resolve_value({"apiKey": "{K}", "endpoint": "https://x"})
        assert result == {"apiKey": "v", "endpoint": "https://x"}

    def test_list_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("K", "v")
        result = resolve_value(["a", "{K}", "b"])
        assert result == ["a", "v", "b"]

    def test_nested_structure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("K", "v")
        result = resolve_value(
            {"headers": {"Authorization": "Bearer {K}"}, "items": ["{K}"]}
        )
        assert result == {
            "headers": {"Authorization": "Bearer v"},
            "items": ["v"],
        }

    def test_non_string_passthrough(self) -> None:
        assert resolve_value(42) == 42
        assert resolve_value(True) is True
        assert resolve_value(None) is None
