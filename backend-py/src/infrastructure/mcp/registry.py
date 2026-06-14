"""MCP tool registry - manages MCP client connections and tool conversion."""

from __future__ import annotations

from typing import Any

import structlog

from src.infrastructure.mcp.client import McpClient
from src.infrastructure.mcp.tool_builder import ToolBuilder
from src.lib.security import resolve_env_vars

logger = structlog.get_logger(__name__)


class McpToolRegistry:
    """Registry for managing MCP client connections and LangChain tools.

    Handles:
    - Creating and caching MCP clients per tool definition
    - Converting discovered MCP tools to LangChain tools
    - Filtering tools by allowedTools list
    - Proper connection lifecycle (connect, disconnect)
    - Tool renaming via actions configuration
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._clients: dict[str, McpClient] = {}
        self._tools: dict[str, list[Any]] = {}

    async def initialize_from_agent(
        self,
        agent_definition: dict[str, Any],
    ) -> dict[str, list[Any]]:
        """Initialize MCP clients from agent definition tools.

        Args:
            agent_definition: Full agent definition dict

        Returns:
            Dict mapping tool_id to list of LangChain tools
        """
        agent_tools = agent_definition.get("tools", [])
        if not agent_tools:
            return {}

        tool_results: dict[str, list[Any]] = {}

        for tool_def in agent_tools:
            tool_type = tool_def.get("type", "")
            if tool_type not in ("mcp", "mcp-http"):
                continue

            tool_id = tool_def.get("id")
            if not tool_id:
                tool_id = tool_def.get("name", "")
                if not tool_id:
                    continue

            try:
                tools = await self._initialize_mcp_tool(tool_def)
                if tools:
                    tool_results[tool_id] = tools
                    logger.info("mcp_tool_registered", tool_id=tool_id, count=len(tools))
            except Exception as e:
                logger.error("mcp_tool_init_failed", tool_id=tool_id, error=str(e))

        self._tools = tool_results
        return tool_results

    async def _initialize_mcp_tool(self, tool_def: dict[str, Any]) -> list[Any]:
        """Initialize a single MCP tool definition.

        Args:
            tool_def: Tool definition dict

        Returns:
            List of LangChain tools
        """
        tool_id = tool_def.get("id", tool_def.get("name", ""))
        server_url = tool_def.get("serverUrl")
        if not server_url:
            return []

        protocol = tool_def.get("protocol", "auto")

        # Resolve headers for env vars
        raw_headers = tool_def.get("headers", {}) or {}
        headers = {}
        for key, value in raw_headers.items():
            resolved = resolve_env_vars(value)
            if resolved:
                headers[key] = resolved

        # Get allowed tools and actions
        allowed_tools = tool_def.get("allowedTools", [])
        actions = tool_def.get("actions", [])

        # Create MCP client
        client = McpClient(
            server_url=server_url,
            headers=headers,
            protocol=protocol,
        )

        try:
            await client.connect()

            # Store client for later use
            self._clients[tool_id] = client

            # Get discovered tools from MCP server
            discovered_tools = client.tools

            # Filter by allowedTools if specified
            if allowed_tools:
                discovered_tools = [
                    t for t in discovered_tools
                    if getattr(t, "name", "") in allowed_tools
                ]

            # Convert to LangChain tools
            langchain_tools = []
            for mcp_tool in discovered_tools:
                # Check if this tool has an action alias
                action = self._find_action(actions, mcp_tool.name)
                if action:
                    tool_name = action.get("name", mcp_tool.name)
                    tool_desc = action.get("description", getattr(mcp_tool, "description", ""))
                else:
                    tool_name = mcp_tool.name
                    tool_desc = getattr(mcp_tool, "description", f"MCP tool: {tool_name}")

                # Create LangChain tool that calls back to this registry's client
                langchain_tool = ToolBuilder.from_mcp_definition(tool_def, client)
                if langchain_tool:
                    # Update name if action renamed it
                    langchain_tool.name = tool_name
                    langchain_tool.description = tool_desc
                    langchain_tools.append(langchain_tool)

            return langchain_tools

        except Exception as e:
            logger.error("mcp_connection_failed", tool_id=tool_id, error=str(e))
            if tool_id in self._clients:
                del self._clients[tool_id]
            return []

    def _find_action(self, actions: list[dict[str, Any]], tool_name: str) -> dict[str, Any] | None:
        """Find an action that aliases a tool.

        Args:
            actions: List of action definitions
            tool_name: Original tool name to find

        Returns:
            Action dict or None
        """
        for action in actions:
            params = action.get("parameters", {})
            if params.get("tool") == tool_name:
                return action
        return None

    def get_tools(self, tool_id: str) -> list[Any]:
        """Get LangChain tools for a tool ID.

        Args:
            tool_id: Tool identifier

        Returns:
            List of LangChain tools
        """
        return self._tools.get(tool_id, [])

    def get_all_tools(self) -> list[Any]:
        """Get all registered LangChain tools.

        Returns:
            Flat list of all LangChain tools
        """
        all_tools: list[Any] = []
        for tools in self._tools.values():
            all_tools.extend(tools)
        return all_tools

    async def disconnect_all(self) -> None:
        """Disconnect all MCP clients."""
        for tool_id, client in list(self._clients.items()):
            try:
                await client.disconnect()
                logger.info("mcp_disconnected", tool_id=tool_id)
            except Exception as e:
                logger.error("mcp_disconnect_failed", tool_id=tool_id, error=str(e))

        self._clients.clear()
        self._tools.clear()

    @property
    def has_mcp_tools(self) -> bool:
        """Check if any MCP tools are registered."""
        return len(self._tools) > 0


# Global registry instance
_mcp_registry: McpToolRegistry | None = None


def get_mcp_registry() -> McpToolRegistry:
    """Get the global MCP registry singleton."""
    global _mcp_registry
    if _mcp_registry is None:
        _mcp_registry = McpToolRegistry()
    return _mcp_registry