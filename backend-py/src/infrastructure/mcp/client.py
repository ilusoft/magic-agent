"""MCP client for connecting to MCP servers."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class McpClient:
    """Client for connecting to MCP servers.

    Uses the official MCP Python SDK for HTTP/SSE protocol support.

    The underlying transport (``streamablehttp_client`` / ``sse_client``)
    and the ``ClientSession`` are async context managers that must
    stay open for the entire lifetime of the connection — not just for
    the initial handshake. We keep both context-manager objects as
    attributes, enter them in :meth:`connect`, and exit them in
    :meth:`disconnect`. The previous implementation only opened the
    transport's ``async with`` around the session constructor, then
    tried to call ``initialize()`` *after* the block had already torn
    the streams down; that produced a ``ClosedResourceError`` with an
    empty message and made every MCP tool call fail silently.
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
        self._transport_cm: Any = None
        self._session_cm: Any = None
        self._tools: list[Any] = []
        self._connected = False

    async def connect(self) -> None:
        """Connect to the MCP server and discover tools."""
        try:
            from mcp import ClientSession
        except ImportError as exc:
            # Surface this loudly — the previous behaviour logged a
            # warning and re-raised, but the workflow_executor caught
            # the ImportError and continued with an empty tool set,
            # so the LLM was called without any MCP tools and the
            # caller never realised the SDK was missing. The ``mcp``
            # package is now a hard dependency, so a missing import
            # here means the runtime environment is broken; tell the
            # operator exactly what to run to fix it.
            raise RuntimeError(
                "The 'mcp' Python SDK is not installed. Install it with "
                "'pip install -e \".[mcp]\"' (or 'pip install mcp>=1.0.0') "
                "so the agent can talk to MCP servers."
            ) from exc

        try:
            # Enter the transport context manager and KEEP it open
            # for the entire client lifetime. We can't use
            # ``async with`` here because ``connect`` must return
            # before ``disconnect`` is called — the MCP registry
            # invokes ``call_tool`` between those two calls.
            if self._protocol == "sse":
                from mcp.client.sse import sse_client
                self._transport_cm = sse_client(
                    url=self._server_url,
                    headers=self._headers,
                )
                streams = await self._transport_cm.__aenter__()
                read_stream, write_stream = streams[0], streams[1]
            else:
                from mcp.client.streamable_http import streamablehttp_client
                self._transport_cm = streamablehttp_client(
                    url=self._server_url,
                    headers=self._headers,
                )
                streams = await self._transport_cm.__aenter__()
                if len(streams) == 3:
                    read_stream, write_stream, _ = streams
                else:
                    read_stream, write_stream = streams

            # ``ClientSession`` is also an async context manager
            # whose ``__aexit__`` shuts down its background tasks and
            # closes the read/write streams. Enter it here and exit
            # it in :meth:`disconnect` so the session stays usable
            # for ``call_tool`` later.
            self._session_cm = ClientSession(read_stream, write_stream)
            self._client = await self._session_cm.__aenter__()

            await self._client.initialize()

            await self._discover_tools()

            self._connected = True
            logger.info("mcp_connected", server_url=self._server_url)

        except Exception as e:
            # Include the exception class name so empty messages
            # (``ClosedResourceError()``, etc.) are still diagnosable
            # in the log line. Without this, the operator sees an
            # ``error=`` with no payload and no way to tell whether
            # the failure was network, auth, or protocol-level.
            logger.error(
                "mcp_connection_failed",
                server_url=self._server_url,
                error=f"{type(e).__name__}: {e}" if str(e) else type(e).__name__,
            )
            await self._cleanup_on_failure()
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
            logger.error(
                "mcp_tool_discovery_failed",
                error=f"{type(e).__name__}: {e}" if str(e) else type(e).__name__,
            )
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
            logger.error(
                "mcp_tool_call_failed",
                tool=tool_name,
                error=f"{type(e).__name__}: {e}" if str(e) else type(e).__name__,
            )
            raise

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        # ``ClientSession`` is closed via its ``__aexit__``; there is
        # no public ``close()`` method in the MCP Python SDK. The
        # transport context manager is exited afterwards so the
        # underlying HTTP/SSE streams are torn down in the right
        # order.
        if self._session_cm is not None:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "mcp_session_close_failed",
                    error=f"{type(e).__name__}: {e}" if str(e) else type(e).__name__,
                )
            self._session_cm = None
            self._client = None
        if self._transport_cm is not None:
            try:
                await self._transport_cm.__aexit__(None, None, None)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "mcp_transport_close_failed",
                    error=f"{type(e).__name__}: {e}" if str(e) else type(e).__name__,
                )
            self._transport_cm = None
        self._connected = False
        logger.info("mcp_disconnected", server_url=self._server_url)

    async def _cleanup_on_failure(self) -> None:
        """Best-effort teardown when :meth:`connect` raises midway.

        Ensures we don't leak a half-opened transport or session
        context manager on the registry's ``_clients`` dict.
        """
        if self._session_cm is not None:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            self._session_cm = None
        if self._transport_cm is not None:
            try:
                await self._transport_cm.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
            self._transport_cm = None
        self._client = None
        self._connected = False

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