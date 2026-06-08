"""MCP transport implementations for HTTP and SSE protocols."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class HttpMcpTransport:
    """HTTP transport for MCP protocol."""

    def __init__(
        self,
        server_url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._server_url = server_url
        self._headers = headers or {}

    async def send_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> Any:
        """Send an HTTP request to the MCP server.

        Args:
            method: HTTP method
            path: Request path
            params: Query parameters
            body: Request body

        Returns:
            Response data
        """
        import httpx

        url = f"{self._server_url.rstrip('/')}/{path.lstrip('/')}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=body if body else None,
                headers=self._headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()


class SseMcpTransport:
    """SSE (Server-Sent Events) transport for MCP protocol.

    Used for server-to-client streaming communication.
    """

    def __init__(
        self,
        server_url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._server_url = server_url
        self._headers = headers or {}

    async def connect(self) -> Any:
        """Connect to the SSE endpoint.

        Returns:
            SSE event stream
        """
        import httpx

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET",
                self._server_url,
                headers=self._headers,
                timeout=None,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        yield line[5:].strip()
                    elif line.startswith("event:"):
                        event_type = line[6:].strip()
                        yield f"event:{event_type}"