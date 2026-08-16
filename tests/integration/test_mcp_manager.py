"""Integration tests for MCP tool manager."""
from __future__ import annotations

import pytest
from agentic_workflow.mcp.manager import MCPToolManager
from unittest.mock import AsyncMock, MagicMock, patch


class TestMCPManagerIntegration:
    """Test MCP tool discovery with local mock server."""

    @pytest.mark.asyncio
    async def test_discover_remote_tools(self):
        manager = MCPToolManager()

        mock_tool = MagicMock()
        mock_tool.name = "remote_test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object", "properties": {"arg": {"type": "string"}}}

        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[mock_tool])
        mock_client.call_tool = AsyncMock(return_value="tool result")

        with patch("fastmcp.Client") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            tools = await manager.discover_remote("https://example.com/mcp")
            assert len(tools) == 1
            assert tools[0].name == "remote_test_tool"

    @pytest.mark.asyncio
    async def test_discover_local_tools(self):
        manager = MCPToolManager()

        mock_tool = MagicMock()
        mock_tool.name = "local_test_tool"
        mock_tool.description = "A local test tool"
        mock_tool.inputSchema = {"type": "object"}

        mock_server = MagicMock()
        mock_server.list_tools = AsyncMock(return_value=[mock_tool])

        with patch("fastmcp.FastMCP") as MockFastMCP:
            MockFastMCP.return_value = mock_server

            tools = await manager.discover_local("test_module")
            assert len(tools) == 1
            assert tools[0].name == "local_test_tool"

    @pytest.mark.asyncio
    async def test_invalid_source_raises_error(self):
        manager = MCPToolManager()
        with pytest.raises(ValueError, match="Unsupported tool source format"):
            await manager.discover("invalid-source")
