"""
In-memory tool registry implementation.

This is the default registry. In production, this could be backed by
Firestore, Redis, or a service catalog for dynamic tool discovery.
"""
from __future__ import annotations

from agentic_workflow.core.interfaces import ITool, IToolRegistry
from agentic_workflow.mcp.manager import MCPToolManager


class InMemoryToolRegistry(IToolRegistry):
    """Thread-safe in-memory tool registry with MCP discovery support."""

    def __init__(self) -> None:
        self._tools: dict[str, ITool] = {}
        self._mcp_manager = MCPToolManager()

    def register(self, tool: ITool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        self._tools.pop(name, None)

    def get(self, name: str) -> ITool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    async def discover(self, source: str) -> list[ITool]:
        """
        Discover tools from an external source.

        Args:
            source: MCP server URL or local module path.

        Returns:
            List of discovered tools.
        """
        if source.startswith("http://") or source.startswith("https://"):
            return await self._mcp_manager.discover_remote(source)
        elif source.startswith("local:"):
            return await self._mcp_manager.discover_local(source[6:])
        else:
            raise ValueError(
                f"Unsupported tool source format: {source}. "
                "Use 'https://...' for remote or 'local:module.path' for local."
            )
