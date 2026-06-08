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
    ) -> Tool | None:
        """Create a Tool from an MCP tool definition.

        Args:
            tool_def: Tool definition dict
            mcp_client: MCP client instance

        Returns:
            LangChain Tool or None
        """
        tool_type = tool_def.get("type", "")
        if tool_type not in ("mcp", "mcp-http"):
            return None

        name = tool_def.get("name", "")
        description = tool_def.get("description", f"MCP tool: {name}")
        allowed_tools = tool_def.get("allowedTools", [])

        async def _run(tool_input: str) -> str:
            # Parse input and call MCP tool
            import json

            if isinstance(tool_input, str):
                try:
                    args = json.loads(tool_input)
                except json.JSONDecodeError:
                    args = {"input": tool_input}
            else:
                args = tool_input

            result = await mcp_client.call_tool(name, args)
            return str(result)

        return Tool(
            name=name,
            description=description,
            func=_run,
        )

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