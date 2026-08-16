"""
MCP tool manager for discovering and wrapping MCP servers.

Supports both local stdio servers and remote HTTP/Streamable HTTP servers.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MCPToolManager:
    """
    Manages MCP tool discovery from local and remote servers.

    This is a lightweight manager that uses FastMCP for protocol handling.
    In production, this would integrate with the official MCP SDK.
    """

    async def discover_remote(self, url: str) -> list[Any]:
        """
        Discover tools from a remote MCP server via Streamable HTTP.

        Args:
            url: The MCP server endpoint URL (e.g., https://.../mcp).

        Returns:
            List of discovered tools (wrapped as ITool implementations).
        """
        try:
            from fastmcp import Client
            from fastmcp.client.transports import StreamableHTTPTransport

            transport = StreamableHTTPTransport(url=url)
            async with Client(transport) as client:
                tools = await client.list_tools()
                return [
                    RemoteMCPTool(
                        name=tool.name,
                        description=tool.description or "",
                        input_schema=tool.inputSchema or {},
                        client=client,
                    )
                    for tool in tools
                ]
        except Exception as e:
            logger.error(f"Failed to discover remote MCP tools from {url}: {e}")
            raise

    async def discover_local(self, module_path: str) -> list[Any]:
        """
        Discover tools from a local MCP server (stdio transport).

        Args:
            module_path: Python module path to the MCP server.

        Returns:
            List of discovered tools.
        """
        try:
            from fastmcp import FastMCP

            server = FastMCP(module_path)
            tools = await server.list_tools()
            return [
                LocalMCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema or {},
                    server=server,
                )
                for tool in tools
            ]
        except Exception as e:
            logger.error(f"Failed to discover local MCP tools from {module_path}: {e}")
            raise


class RemoteMCPTool:
    """Wrapper for a remote MCP tool."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        client: Any,
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self._client = client

    @property
    def schema(self) -> dict[str, Any]:
        return self.input_schema

    async def execute(self, arguments: dict[str, Any]) -> str:
        result = await self._client.call_tool(self.name, arguments)
        return str(result)


class LocalMCPTool:
    """Wrapper for a local stdio MCP tool."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        server: Any,
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self._server = server

    @property
    def schema(self) -> dict[str, Any]:
        return self.input_schema

    async def execute(self, arguments: dict[str, Any]) -> str:
        result = await self._server.call_tool(self.name, arguments)
        return str(result)
