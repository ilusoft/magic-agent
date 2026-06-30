"""Tool builder for creating LangChain tools from MCP definitions."""

from __future__ import annotations

from typing import Any, Callable

from langchain_core.tools import Tool

from src.lib.security import resolve_env_vars


class ToolBuilder:
    """Builder for creating tools from definitions."""

    @staticmethod
    def from_http_definition(
        tool_def: dict[str, Any],
        default_headers: dict[str, str] | None = None,
    ) -> Tool | None:
        """Create a Tool from an HTTP tool definition.

        Args:
            tool_def: Tool definition dict
            default_headers: Default headers to use

        Returns:
            LangChain Tool or None
        """
        tool_type = tool_def.get("type", "")
        if tool_type != "http":
            return None

        name = tool_def.get("name", "")
        description = tool_def.get("description", f"HTTP tool: {name}")
        base_url = tool_def.get("baseUrl")

        if not name or not base_url:
            return None

        headers = tool_def.get("headers", {}) or {}
        if default_headers:
            headers = {**default_headers, **headers}

        async def _run(tool_input: str) -> str:
            import httpx

            resolved_url = resolve_env_vars(base_url)
            resolved_headers = {k: resolve_env_vars(v) for k, v in headers.items()}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    resolved_url,
                    json={"input": tool_input},
                    headers=resolved_headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.text

        return Tool(
            name=name,
            description=description,
            func=_run,
        )

    @staticmethod
    def from_mcp_definition(
        tool_def: dict[str, Any],
        mcp_client: Any,
        mcp_tool_name: str | None = None,
    ) -> Tool | None:
        """Create a Tool from an MCP tool definition.

        Args:
            tool_def: Tool definition dict
            mcp_client: MCP client instance
            mcp_tool_name: Optional real MCP tool name to invoke. When
                an MCP server exposes multiple tools and the agent
                definition renames them via ``actions[].parameters.tool``,
                each LangChain tool must call the underlying server by
                the *real* tool name (``tavily_search``) even though the
                LangChain tool is exposed to the model as the renamed
                name (``web_search``). Falls back to ``tool_def['name']``
                when omitted for backward compatibility.

        Returns:
            LangChain Tool (StructuredTool under the hood) or None
        """
        from pydantic import BaseModel, ConfigDict, Field

        from langchain_core.tools import StructuredTool

        tool_type = tool_def.get("type", "")
        if tool_type not in ("mcp", "mcp-http"):
            return None

        name = tool_def.get("name", "")
        description = tool_def.get("description", f"MCP tool: {name}")
        # ``mcp_tool_name`` overrides the name the underlying
        # ``_run`` closure passes to ``mcp_client.call_tool`` so that
        # multi-tool MCP servers can be aliased via ``actions`` without
        # every renamed LangChain tool calling the same underlying tool.
        invoke_name = mcp_tool_name or name

        # Permissive input schema. We don't know the MCP tool's exact
        # ``inputSchema`` until runtime (it's advertised by
        # ``list_tools()``), so we accept arbitrary kwargs and let
        # the MCP server do its own validation.
        #
        # The schema must declare at least one field: LangChain's
        # ``StructuredTool._to_args_and_kwargs`` short-circuits to
        # ``(), {}`` (and drops the entire input) when
        # ``get_fields(args_schema)`` is empty. With ``extra="allow"``,
        # the LLM's structured args (e.g. ``{"query": "..."}`` for
        # ``tavily_search``) are kept as Pydantic "extra" fields and
        # routed through to the coroutine as ``**kwargs``.
        #
        # The legacy ``Tool`` class can't be used here: its
        # ``_to_args_and_kwargs`` collapses a single-key dict to its
        # first value, which is the bug that originally surfaced as
        # empty step output.
        class _McpToolInput(BaseModel):
            model_config = ConfigDict(extra="allow")
            # Wrapper field. The LLM never sets it (it just sends the
            # MCP tool's structured args directly), but it satisfies
            # the "at least one declared field" requirement above.
            # The coroutine falls back to it if a caller does pass
            # ``{"mcp_call_args": {...}}`` explicitly.
            mcp_call_args: dict[str, Any] = Field(
                default_factory=dict,
                description=(
                    "Optional wrapper for callers that prefer to send "
                    "all MCP arguments inside a single field. The LLM "
                    "tool-calling path doesn't use this; it sends the "
                    "MCP tool's inputSchema fields directly as kwargs."
                ),
            )

        async def _run(mcp_call_args: dict[str, Any], **kwargs: Any) -> str:
            # The LLM's structured args arrive as ``**kwargs`` (every
            # field on the input that isn't the declared wrapper).
            # Fall back to the wrapper for callers that pass
            # ``{"mcp_call_args": {...}}`` directly.
            import json

            if kwargs:
                raw_args = dict(kwargs)
            elif mcp_call_args:
                raw_args = dict(mcp_call_args)
            else:
                raw_args = {}

            # ``StructuredTool`` does JSON-roundtrip the input for some
            # types, so nested dicts/lists may come back as strings.
            # Normalise so the MCP server sees proper JSON.
            args: dict[str, Any] = {}
            for key, value in raw_args.items():
                if isinstance(value, str):
                    try:
                        args[key] = json.loads(value)
                        continue
                    except (json.JSONDecodeError, ValueError):
                        pass
                args[key] = value

            result = await mcp_client.call_tool(invoke_name, args)
            return str(result)

        # ``StructuredTool`` requires a sync ``func`` even when only
        # the coroutine is exercised; point it at a stub that fails
        # loudly so any accidental sync invocation surfaces the
        # misconfiguration instead of silently blocking the loop.
        def _sync_run(
            mcp_call_args: dict[str, Any], **_kwargs: Any
        ) -> str:
            raise NotImplementedError(
                "MCP tools are async-only; use ainvoke() or bind_tools() in an async loop."
            )

        tool = StructuredTool(
            name=name,
            description=description,
            args_schema=_McpToolInput,
            func=_sync_run,
            coroutine=_run,
        )
        # The registry overrides ``.name`` and ``.description`` after
        # this returns to apply ``actions[].name`` aliases; preserve
        # them here so the override is a no-op when no alias is
        # configured (StructuredTool stores the name on the object
        # the same way legacy ``Tool`` does).
        return tool

    @staticmethod
    def from_definition(
        tool_def: dict[str, Any],
        mcp_client: Any | None = None,
        default_headers: dict[str, str] | None = None,
    ) -> Tool | None:
        """Create a Tool from any supported tool definition.

        Args:
            tool_def: Tool definition dict
            mcp_client: Optional MCP client for MCP tools
            default_headers: Default headers for HTTP tools

        Returns:
            LangChain Tool or None
        """
        tool_type = tool_def.get("type", "")

        if tool_type in ("mcp", "mcp-http"):
            if mcp_client:
                return ToolBuilder.from_mcp_definition(tool_def, mcp_client)
            return None

        if tool_type == "http":
            return ToolBuilder.from_http_definition(tool_def, default_headers)

        return None

    @staticmethod
    def from_definitions(
        tool_defs: list[dict[str, Any]],
        mcp_client: Any | None = None,
        default_headers: dict[str, str] | None = None,
    ) -> list[Tool]:
        """Create multiple Tools from definitions.

        Args:
            tool_defs: List of tool definition dicts
            mcp_client: Optional MCP client
            default_headers: Default headers

        Returns:
            List of LangChain Tools
        """
        tools = []
        for tool_def in tool_defs:
            tool = ToolBuilder.from_definition(
                tool_def,
                mcp_client=mcp_client,
                default_headers=default_headers,
            )
            if tool:
                tools.append(tool)
        return tools