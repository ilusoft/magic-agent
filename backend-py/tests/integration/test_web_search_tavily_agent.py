"""End-to-end validation of the Tavily web-search agent definition.

The user added ``web-search-tavily-qwen-local`` to
``configs/agents/agents.json`` to exercise the OpenAI-compatible
provider + MCP tool calling pipeline against a local Qwen LLM and the
Tavily MCP server. After the global profiles/tools refactor (phase
8/9) the LLM config lives in the document-level ``llmProfiles`` map
and the MCP tool config lives in the document-level ``tools`` map;
this module verifies both lookups still produce an openai-compatible
chat config and a renamed LangChain toolset without ever hitting a
real network endpoint.

The registry/network portion is exercised in isolation against a
fake ``McpClient`` so we don't need the ``mcp`` Python SDK to be
installed (or the Tavily server to be reachable) for the test to
run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.agent_runtime.workflow_executor import WorkflowExecutor
from src.infrastructure.mcp.registry import McpToolRegistry
from src.infrastructure.mcp.tool_builder import ToolBuilder


_REPO_ROOT = Path(__file__).resolve().parents[3]
_AGENTS_JSON = _REPO_ROOT / "configs" / "agents" / "agents.json"


def _load_document() -> dict[str, Any]:
    assert _AGENTS_JSON.exists(), f"missing {_AGENTS_JSON}"
    with _AGENTS_JSON.open() as fh:
        return json.load(fh)


def _load_web_search_agent() -> dict[str, Any]:
    document = _load_document()
    agent = next(
        (a for a in document["agents"] if a.get("id") == "web-search-tavily-qwen-local"),
        None,
    )
    assert agent is not None, "web-search-tavily-qwen-local not in agents.json"
    return agent


def _web_search_profile(document: dict[str, Any]) -> dict[str, Any]:
    """The LLM profile referenced by the web-search agent's steps."""
    profiles = document.get("llmProfiles", {})
    agent = _load_web_search_agent()
    # All steps in this agent reference the same profile. Pull the
    # profileId from the first agent step and look it up.
    for step in agent.get("steps", []):
        profile_id = (step.get("llmConfig") or {}).get("profileId")
        if profile_id:
            profile = profiles.get(profile_id)
            if profile is not None:
                return profile
    raise AssertionError(
        "web-search-tavily-qwen-local has no agent step with a "
        "profileId; expected the migration to wire it up."
    )


def _tavily_tool_definition(document: dict[str, Any]) -> dict[str, Any]:
    """The MCP tool definition in the document-level ``tools`` map."""
    tools = document.get("tools", {})
    tavily = tools.get("tavily-mcp")
    assert tavily is not None, (
        "tavily-mcp must live in the document-level tools map (post-refactor)"
    )
    return tavily


class TestWebSearchAgentConfiguration:
    """Static checks on the migrated JSON definition itself."""

    def test_llm_profile_is_openai_compatible(self) -> None:
        document = _load_document()
        profile = _web_search_profile(document)
        assert profile["provider"] == "openai-compatible", (
            "The web-search agent's profile must declare provider "
            "openai-compatible so WorkflowExecutor._resolve_step_llm_config "
            "routes the chat model through the OpenAI-compatible factory branch."
        )

    def test_base_url_and_model_are_set(self) -> None:
        document = _load_document()
        profile = _web_search_profile(document)
        assert profile["baseUrl"] == "http://127.0.0.1:8000/v1"
        assert profile["model"] == "Qwen3.6-35B-A3B-OptiQ-4bit"

    def test_llm_profile_api_key_is_not_a_secret_literal(self) -> None:
        """If the operator committed a hardcoded API key we surface
        a warning so the same regression can't sneak back in. The
        ``${ENV_VAR}`` and ``{ENV_VAR}`` placeholder forms are
        preferred.
        """
        document = _load_document()
        profile = _web_search_profile(document)
        api_key = profile.get("apiKey", "")

        is_placeholder = (
            (api_key.startswith("${") and api_key.endswith("}"))
            or (api_key.startswith("{") and api_key.endswith("}"))
        )

        if not is_placeholder:
            import warnings

            warnings.warn(
                "llmProfiles[...].apiKey is a hardcoded value; "
                "use '${OPENAI_API_KEY}' to keep the secret out of "
                "version control.",
                stacklevel=2,
            )

    def test_tavily_tool_definition_in_document_pool(self) -> None:
        document = _load_document()
        tavily = _tavily_tool_definition(document)
        assert "tavilyApiKey" in tavily["serverUrl"]
        assert tavily["allowedTools"] == ["tavily_search", "tavily_extract"]
        action_names = {a["name"] for a in tavily.get("actions", [])}
        assert {"web_search", "fetch_page"}.issubset(action_names)

    def test_search_step_references_mcp_tool(self) -> None:
        agent = _load_web_search_agent()
        search_step = next(
            s for s in agent["steps"] if s.get("name") == "web-search-agent"
        )
        assert "tavily-mcp" in search_step["tools"]


class TestResolveLLMConfigForWebSearchAgent:
    """``WorkflowExecutor._resolve_step_llm_config`` must look up the
    document-level profile, merge any inline overrides, and return an
    openai-compatible chat config with the right ``base_url`` /
    ``model``.
    """

    def setup_method(self) -> None:
        self.executor = WorkflowExecutor()

    def test_resolve_step_llm_config_uses_openai_compatible(self) -> None:
        document = _load_document()
        agent = _load_web_search_agent()
        search_step = next(
            s for s in agent["steps"] if s.get("name") == "web-search-agent"
        )
        llm_config = self.executor._resolve_step_llm_config(search_step, document)

        assert llm_config is not None
        assert llm_config["provider"] == "openai-compatible"
        assert llm_config["model"] == "Qwen3.6-35B-A3B-OptiQ-4bit"
        assert llm_config["base_url"] == "http://127.0.0.1:8000/v1"
        # Must NOT have Azure fields populated — the factory would
        # then try to use the AzureOpenAI branch and fail.
        assert not llm_config.get("endpoint")
        assert not llm_config.get("deployment")

    def test_default_parameters_api_key_env_placeholder_is_resolved(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``llmProfiles.<id>.apiKey = "${OPENAI_API_KEY}"`` must
        resolve to the real env-var value before the LLM factory
        sees it. Without this, the local Qwen server rejects the
        literal ``${OPENAI_API_KEY}`` string with a 401
        ``Invalid API key`` error.

        We build a synthetic document with the placeholder so the
        test is independent of whatever the checked-in
        ``agents.json`` happens to have. ``_resolve_llm_config`` (not
        ``_resolve_step_llm_config``) is the entry point that runs
        the ``${ENV_VAR}`` substitution before returning.
        """
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-from-env")

        document = {
            "llmProfiles": {
                "synthetic": {
                    "provider": "openai-compatible",
                    "baseUrl": "http://127.0.0.1:8000/v1",
                    "model": "Qwen3.6-35B-A3B-OptiQ-4bit",
                    "apiKey": "${OPENAI_API_KEY}",
                }
            }
        }
        step = {"name": "synthetic-chat", "llmConfig": {"profileId": "synthetic"}}

        llm_config = self.executor._resolve_llm_config({}, step=step, document=document)

        assert llm_config["api_key"] == "sk-test-from-env"
        # Resolved value must NOT be the raw placeholder string.
        assert "${" not in (llm_config.get("api_key") or "")

    def test_unresolved_api_key_placeholder_does_not_leak(self) -> None:
        """When the env var is unset and the profile only declares a
        ``${VAR}`` placeholder, the resolver must clear the key so
        the LLM factory can fall back to its settings/env-var chain.
        Forwarding the raw ``${OPENAI_API_KEY}`` string would
        produce a 401 against any auth-enabled local server.
        """
        document = {
            "llmProfiles": {
                "synthetic": {
                    "provider": "openai-compatible",
                    "baseUrl": "http://127.0.0.1:8000/v1",
                    "model": "Qwen3.6-35B-A3B-OptiQ-4bit",
                    "apiKey": "${UNSET_ENV_VAR_FOR_TEST}",
                }
            }
        }
        step = {"name": "synthetic-chat", "llmConfig": {"profileId": "synthetic"}}

        keys = (
            "OPENAI_API_KEY",
            "LLM_API_KEY",
            "AZURE_OPENAI_APIKEY",
            "UNSET_ENV_VAR_FOR_TEST",
        )
        original = {k: os.environ.pop(k, None) for k in keys}
        try:
            llm_config = self.executor._resolve_llm_config({}, step=step, document=document)
        finally:
            for k, v in original.items():
                if v is not None:
                    os.environ[k] = v

        assert not llm_config.get("api_key"), (
            f"unresolved placeholder leaked into llm_config: "
            f"{llm_config.get('api_key')!r}"
        )

    def test_profile_api_key_overrides_default_parameters(self) -> None:
        """A document-level ``llmProfiles.<id>.apiKey`` overrides any
        ``defaultParameters.apiKey`` so callers can put a hardcoded
        key in the profile when they really want to.
        """
        document = {
            "defaultParameters": {"apiKey": "from-default-params"},
            "llmProfiles": {
                "synthetic": {
                    "provider": "openai-compatible",
                    "baseUrl": "http://127.0.0.1:8000/v1",
                    "model": "Qwen3.6-35B-A3B-OptiQ-4bit",
                    "apiKey": "from-profile",
                }
            },
        }
        step = {"name": "synthetic-chat", "llmConfig": {"profileId": "synthetic"}}

        llm_config = self.executor._resolve_llm_config({}, step=step, document=document)

        assert llm_config["api_key"] == "from-profile"

    def test_default_parameters_plain_api_key_is_accepted(self) -> None:
        """A plain (non-placeholder) string in the profile's
        ``apiKey`` is also accepted so authors don't have to wrap
        every value in ``${...}``.
        """
        document = {
            "llmProfiles": {
                "synthetic": {
                    "provider": "openai-compatible",
                    "baseUrl": "http://127.0.0.1:8000/v1",
                    "model": "Qwen3.6-35B-A3B-OptiQ-4bit",
                    "apiKey": "plain-value",
                }
            },
        }
        step = {"name": "synthetic-chat", "llmConfig": {"profileId": "synthetic"}}

        llm_config = self.executor._resolve_llm_config({}, step=step, document=document)

        assert llm_config["api_key"] == "plain-value"


class _FakeMcpClient:
    """In-memory stand-in for ``McpClient`` that records the names of
    the tools it was asked to invoke."""

    def __init__(self) -> None:
        self._connected = True
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._tools = [
            SimpleNamespace(
                name="tavily_search",
                description="Search the web for information.",
            ),
            SimpleNamespace(
                name="tavily_extract",
                description="Extract text from a list of URLs.",
            ),
        ]

    async def connect(self) -> None:  # pragma: no cover - unused
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    @property
    def tools(self) -> list[SimpleNamespace]:
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, dict(arguments)))
        # ``McpClient.call_tool`` unwraps ``result.content``; mirror
        # that shape so the same code path runs.
        return SimpleNamespace(content=f"<<{name} payload {arguments}>>")


class TestMcpToolRenaming:
    """Regression: action aliases must call the *real* MCP tool name."""

    @pytest.mark.asyncio
    async def test_renamed_tools_invoke_real_mcp_names(self) -> None:
        document = _load_document()
        tavily_def = _tavily_tool_definition(document)

        # Run the same tool-building loop ``McpToolRegistry`` uses,
        # but with a fake client so we don't need the real MCP SDK
        # installed for the test to run.
        client = _FakeMcpClient()
        allowed = tavily_def["allowedTools"]
        actions = tavily_def.get("actions", [])

        discovered = [t for t in client.tools if t.name in allowed]
        langchain_tools: list[Any] = []
        for mcp_tool in discovered:
            action = next(
                (a for a in actions if a.get("parameters", {}).get("tool") == mcp_tool.name),
                None,
            )
            tool = ToolBuilder.from_mcp_definition(
                tavily_def, client, mcp_tool_name=mcp_tool.name
            )
            assert tool is not None
            if action:
                tool.name = action["name"]
                tool.description = action["description"]
            langchain_tools.append(tool)

        names = {tool.name for tool in langchain_tools}
        assert names == {"web_search", "fetch_page"}

        # Exercise the async path the workflow executor uses. The
        # MCP tools are now StructuredTool-backed (the legacy
        # ``Tool`` class collapsed a single-key dict to its first
        # value and silently dropped the LLM's structured args, so
        # this is a real regression test for the empty-output bug).
        # The coroutine expects ``**kwargs`` populated from the
        # tool's ``inputSchema``; the fake MCP server records the
        # structured call so we can assert the right field name
        # survived the round-trip.
        import asyncio

        await langchain_tools[0].ainvoke({"query": "capital of France"})
        await langchain_tools[1].ainvoke({"urls": ["https://example.com"]})

        invoked = [name for name, _ in client.calls]
        assert invoked == ["tavily_search", "tavily_extract"], (
            "Renamed LangChain tools must invoke the underlying MCP tool "
            "by its real server-side name, not the renamed LangChain name."
        )
        # The structured args must also survive the LangChain
        # ``ainvoke`` round-trip. Pre-fix, the legacy ``Tool``
        # backward-compat path collapsed a single-key dict to its
        # first value, so the MCP server received ``{"input": ...}``
        # instead of ``{"query": ...}`` and Tavily returned an error
        # — which is what made the step output come back empty.
        first_call = client.calls[0]
        second_call = client.calls[1]
        assert first_call[1] == {"query": "capital of France"}, first_call
        assert second_call[1] == {"urls": ["https://example.com"]}, second_call

    @pytest.mark.asyncio
    async def test_registry_builds_renamed_tools(self) -> None:
        """``McpToolRegistry._initialize_mcp_tool`` must follow the
        same contract: rename via ``actions`` and invoke by real name.

        We bypass the real MCP SDK handshake by stubbing
        ``McpClient.connect`` so the test runs without the optional
        ``mcp`` dependency installed or the Tavily server reachable.
        """
        from src.infrastructure.mcp import client as mcp_client_module

        document = _load_document()
        tavily_def = _tavily_tool_definition(document)

        fake = _FakeMcpClient()

        class _StubSession:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            async def initialize(self) -> None:
                return None

            async def list_tools(self):
                return SimpleNamespace(tools=fake.tools)

            async def call_tool(self, name, arguments):
                return await fake.call_tool(name, arguments)

        async def _fake_connect(self) -> None:  # type: ignore[no-untyped-def]
            self._client = _StubSession()
            self._connected = True
            await self._discover_tools()

        mcp_client_module.McpClient.connect = _fake_connect  # type: ignore[method-assign]
        mcp_client_module.McpClient.__init__ = (  # type: ignore[method-assign]
            lambda self, server_url, headers=None, protocol="auto": None
        )

        try:
            registry = McpToolRegistry()
            tools = await registry._initialize_mcp_tool(tavily_def)
        finally:
            # Restore the original methods so we don't leak state into
            # other tests that might import the same module.
            del mcp_client_module.McpClient.connect
            del mcp_client_module.McpClient.__init__

        names = {tool.name for tool in tools}
        assert names == {"web_search", "fetch_page"}

        await tools[0].ainvoke({"query": "weather in Paris"})
        await tools[1].ainvoke({"urls": ["https://example.com"]})

        invoked = [name for name, _ in fake.calls]
        assert invoked == ["tavily_search", "tavily_extract"]
        # Structured args must survive the round-trip — see the
        # matching assertion in
        # ``TestMcpToolRenaming.test_renamed_tools_invoke_real_mcp_names``
        # for context on why this matters.
        first_call = fake.calls[0]
        second_call = fake.calls[1]
        assert first_call[1] == {"query": "weather in Paris"}, first_call
        assert second_call[1] == {"urls": ["https://example.com"]}, second_call
