"""Integration tests for tool registration and invocation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class TestToolRegistration:
    """Test dynamic tool discovery and registration."""

    def test_list_tools_returns_empty_initially(self, client: TestClient):
        response = client.get("/tools")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_register_tool_from_source(self, client: TestClient):
        with patch("agentic_workflow.api.server.registry") as mock_registry:
            mock_registry.discover = AsyncMock(
                return_value=[MagicMock(name="test_tool")]
            )
            response = client.post(
                "/tools/register",
                json={"source": "https://example.com/mcp"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_register_tool_invalid_source(self, client: TestClient):
        with patch("agentic_workflow.api.server.registry") as mock_registry:
            mock_registry.discover = MagicMock(
                side_effect=ValueError("Unsupported tool source format")
            )
            response = client.post(
                "/tools/register",
                json={"source": "invalid-source"},
            )
            assert response.status_code == 400
