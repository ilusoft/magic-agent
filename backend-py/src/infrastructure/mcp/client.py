"""MCP client for connecting to MCP servers."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class McpClient:
    """Client for connecting to MCP servers.

    Uses the official MCP Python SDK for HTTP/SSE protocol support.
    """

    def __init__(
        self,
        server_url: str,
        headers: dict[str, str] | None = None,
        protocol: str = "auto",
    ) -> None:
        """Initialize MCP client.

        Args:
            server_url: MCP server URL
            headers: Optional HTTP headers (for auth)
            protocol: Protocol to use (auto, http, sse)
        """
        self._server_url = server_url
        self._headers = headers or {}
        self._protocol = protocol
        self._client: Any = None
        self._tools: list[Any] = []
        self._connected = False

    async def connect(self) -> None:
        """Connect to the MCP server and discover tools."""
        try:
            from mcp import ClientSession

            if self._protocol == "sse":
                from mcp.client.sse import sse_client
                async with sse_client(
                    url=self._server_url,
                    headers=self._headers,
                ) as (read_stream, write_stream):
                    self._client = ClientSession(
                        read_stream=read_stream,
                        write_stream=write_stream,
                    )
            else:
                from mcp.client.streamable_http import streamablehttp_client
                async with streamablehttp_client(
                    url=self._server_url,
                    headers=self._headers,
                ) as streams:
                    if len(streams) == 3:
                        read_stream, write_stream, _ = streams
                    else:
                        read_stream, write_stream = streams
                    self._client = ClientSession(
                        read_stream=read_stream,
                        write_stream=write_stream,
                    )

            await self._client.initialize()

            await self._discover_tools()

            self._connected = True
            logger.info("mcp_connected", server_url=self._server_url)

        except ImportError:
            logger.warning("mcp_sdk_not_available", server_url=self._server_url)
            raise
        except Exception as e:
            logger.error("mcp_connection_failed", server_url=self._server_url, error=str(e))
            raise

    async def _discover_tools(self) -> None:
        """Discover tools from the MCP server."""
        if not self._client:
            return

        try:
            response = await self._client.list_tools()
            self._tools = response.tools
            logger.info("mcp_tools_discovered", count=len(self._tools))
        except Exception as e:
            logger.error("mcp_tool_discovery_failed", error=str(e))
            self._tools = []

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if not self._connected or not self._client:
            raise RuntimeError("MCP client not connected")

        try:
            result = await self._client.call_tool(tool_name, arguments)
            return result.content
        except Exception as e:
            logger.error("mcp_tool_call_failed", tool=tool_name, error=str(e))
            raise

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("mcp_disconnected", server_url=self._server_url)

    @property
    def tools(self) -> list[Any]:
        """Get discovered tools."""
        return self._tools

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected


class McpToolBuilder:
    """Builder for converting MCP tools to LangChain tools."""

    @staticmethod
    def to_langchain_tool(mcp_tool: Any) -> Any:
        """Convert an MCP tool to a LangChain tool.

        Args:
            mcp_tool: MCP tool definition

        Returns:
            LangChain Tool
        """
        from langchain_core.tools import Tool

        async def _run(tool_input: str | dict[str, Any]) -> str:
            if isinstance(tool_input, str):
                import json
                arguments = json.loads(tool_input)
            else:
                arguments = tool_input

            # This would need an MCP client instance
            # The actual implementation depends on how tools are used
            return f"MCP tool {mcp_tool.name} called with {arguments}"

        return Tool(
            name=mcp_tool.name,
            description=mcp_tool.description or f"MCP tool: {mcp_tool.name}",
            func=_run,
        )

    @staticmethod
    def to_langchain_tools(mcp_tools: list[Any]) -> list[Any]:
        """Convert multiple MCP tools to LangChain tools.

        Args:
            mcp_tools: List of MCP tool definitions

        Returns:
            List of LangChain Tools
        """
        return [McpToolBuilder.to_langchain_tool(t) for t in mcp_tools]