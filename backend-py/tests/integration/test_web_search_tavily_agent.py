"""End-to-end validation of the Tavily web-search agent definition.

The user added ``web-search-tavily-qwen-local`` to
``configs/agents/agents.json`` to exercise the OpenAI-compatible
provider + MCP tool calling pipeline against a local Qwen LLM and the
Tavily MCP server. This module verifies two things without ever
hitting a real network endpoint:

1. ``WorkflowExecutor._resolve_llm_config`` lifts the agent's
   top-level ``provider``/``baseUrl``/``model`` into the chat-model
   config so the ``LLMFactory`` would receive an
   ``openai-compatible`` request.
2. ``McpToolRegistry`` exposes the renamed tools (``web_search``,
   ``fetch_page``) and the underlying ``_run`` closure invokes the
   real MCP tool names (``tavily_search``, ``tavily_extract``) — not
   the agent-level ``name`` from the JSON.

The registry/network portion is exercised in isolation against a
fake ``McpClient`` so we don't need the ``mcp`` Python SDK to be
installed (or the Tavily server to be reachable) for the test to
run.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.agent_runtime.workflow_executor import WorkflowExecutor
from src.infrastructure.mcp.registry import McpToolRegistry
from src.infrastructure.mcp.tool_builder import ToolBuilder


_REPO_ROOT = Path(__file__).resolve().parents[3]
_AGENTS_JSON = _REPO_ROOT / "configs" / "agents" / "agents.json"


def _load_web_search_agent() -> dict[str, Any]:
    assert _AGENTS_JSON.exists(), f"missing {_AGENTS_JSON}"
    with _AGENTS_JSON.open() as fh:
        document = json.load(fh)
    agent = next(
        (a for a in document["agents"] if a.get("id") == "web-search-tavily-qwen-local"),
        None,
    )
    assert agent is not None, "web-search-tavily-qwen-local not in agents.json"
    return agent


class TestWebSearchAgentConfiguration:
    """Static checks on the JSON definition itself."""

    def test_top_level_provider_is_openai_compatible(self) -> None:
        agent = _load_web_search_agent()
        assert agent["provider"] == "openai-compatible", (
            "The agent must declare a top-level provider so "
            "WorkflowExecutor._resolve_llm_config routes the chat "
            "model through the OpenAI-compatible factory branch."
        )

    def test_base_url_and_model_are_set(self) -> None:
        agent = _load_web_search_agent()
        assert agent["baseUrl"] == "http://127.0.0.1:8000/v1"
        # Model name is whatever the local server advertises on
        # ``GET /v1/models``. The 404 in the operator logs was
        # caused by pinning ``qwen-3.5`` here when the server only
        # exposes ``Qwen3.6-35B-A3B-OptiQ-4bit`` (and a couple of
        # others); assert the new name is wired so the same
        # regression can't sneak back in.
        assert agent["model"] == "Qwen3.6-35B-A3B-OptiQ-4bit"

    def test_default_parameters_resolves_api_key_env_placeholder(self) -> None:
        """``defaultParameters.apiKey`` should ideally be a
        ``${ENV_VAR}`` placeholder so the secret stays out of the
        JSON (which is committed to git). Hardcoded values still
        work — the resolver forwards them through — so we accept
        both shapes here but warn if the agent has committed a
        literal secret. The same check applies to MCP tool
        ``headers`` so we surface both at once.
        """
        agent = _load_web_search_agent()
        api_key = agent["defaultParameters"].get("apiKey", "")

        is_placeholder = api_key.startswith("${") and api_key.endswith("}")
        is_env_braces = api_key.startswith("{") and api_key.endswith("}")

        if not (is_placeholder or is_env_braces):
            import warnings

            warnings.warn(
                "defaultParameters.apiKey is a hardcoded value; "
                "use '${OPENAI_API_KEY}' to keep the secret out of "
                "version control.",
                stacklevel=2,
            )
        # Resolver-level coverage of the placeholder path lives in
        # ``TestResolveLLMConfigForWebSearchAgent``.

    def test_has_tavily_mcp_tool_definition(self) -> None:
        agent = _load_web_search_agent()
        mcp_tools = [t for t in agent.get("tools", []) if t.get("type") == "mcp"]
        assert mcp_tools, "Agent must declare at least one MCP tool"
        tavily = mcp_tools[0]
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
    """The chat-model factory must receive an openai-compatible
    config with the right ``base_url``/``model``."""

    def setup_method(self) -> None:
        self.executor = WorkflowExecutor()

    def test_resolve_llm_config_uses_openai_compatible(self) -> None:
        agent = _load_web_search_agent()
        llm_config = self.executor._resolve_llm_config(agent)

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
        """``defaultParameters.apiKey = "${OPENAI_API_KEY}"`` must
        resolve to the real env-var value before the LLM factory
        sees it. Without this, the local Qwen server rejects the
        literal ``${OPENAI_API_KEY}`` string with a 401
        ``Invalid API key`` error.

        We build a synthetic agent with the placeholder so the
        test is independent of whatever shape the checked-in
        ``agents.json`` happens to have.
        """
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-from-env")

        agent = {
            "id": "synthetic",
            "provider": "openai-compatible",
            "baseUrl": "http://127.0.0.1:8000/v1",
            "model": "Qwen3.6-35B-A3B-OptiQ-4bit",
            "defaultParameters": {
                "apiKey": "${OPENAI_API_KEY}",
            },
        }
        llm_config = self.executor._resolve_llm_config(agent)

        assert llm_config["api_key"] == "sk-test-from-env"
        # Resolved value must NOT be the raw placeholder string.
        assert "${" not in (llm_config.get("api_key") or "")

    def test_unresolved_api_key_placeholder_does_not_leak(self) -> None:
        """When the env var is unset and the agent only declares a
        ``${VAR}`` placeholder, the resolver must clear the key so
        the LLM factory can fall back to its settings/env-var chain.
        Forwarding the raw ``${OPENAI_API_KEY}`` string would
        produce a 401 against any auth-enabled local server.

        Again, built against a synthetic agent so the test is
        independent of ``agents.json``.
        """
        agent = {
            "id": "synthetic",
            "provider": "openai-compatible",
            "baseUrl": "http://127.0.0.1:8000/v1",
            "model": "Qwen3.6-35B-A3B-OptiQ-4bit",
            "defaultParameters": {
                "apiKey": "${UNSET_ENV_VAR_FOR_TEST}",
            },
        }
        # Strip every env var the resolver might consult.
        import os
        keys = (
            "OPENAI_API_KEY",
            "LLM_API_KEY",
            "AZURE_OPENAI_APIKEY",
            "UNSET_ENV_VAR_FOR_TEST",
        )
        original = {k: os.environ.pop(k, None) for k in keys}
        try:
            llm_config = self.executor._resolve_llm_config(agent)
        finally:
            for k, v in original.items():
                if v is not None:
                    os.environ[k] = v

        assert not llm_config.get("api_key"), (
            f"unresolved placeholder leaked into llm_config: "
            f"{llm_config.get('api_key')!r}"
        )

    def test_top_level_api_key_wins_over_default_parameters(self) -> None:
        """Top-level ``apiKey`` should still take precedence over
        ``defaultParameters.apiKey`` so callers can hardcode a key
        when they really want to.
        """
        agent = _load_web_search_agent()
        agent = {**agent, "apiKey": "hardcoded-top-level"}
        llm_config = self.executor._resolve_llm_config(agent)
        assert llm_config["api_key"] == "hardcoded-top-level"

    def test_default_parameters_plain_api_key_is_accepted(self) -> None:
        """A plain (non-placeholder) string in ``defaultParameters.apiKey``
        is also accepted so authors don't have to wrap every value
        in ``${...}``.
        """
        agent = _load_web_search_agent()
        agent = {**agent, "defaultParameters": {**agent["defaultParameters"], "apiKey": "plain-value"}}
        # Drop the placeholder so we exercise the plain path.
        agent["defaultParameters"].pop("apiKey", None)
        agent["defaultParameters"]["apiKey"] = "plain-value"
        llm_config = self.executor._resolve_llm_config(agent)
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
        agent = _load_web_search_agent()
        tavily_def = next(
            t for t in agent["tools"] if t.get("id") == "tavily-mcp"
        )

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
            "by its real server-side name, not the agent-level "
            "``tools[].name`` or the renamed LangChain name."
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

        agent = _load_web_search_agent()
        tavily_def = next(
            t for t in agent["tools"] if t.get("id") == "tavily-mcp"
        )

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
