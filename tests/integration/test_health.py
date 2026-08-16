"""Integration tests for the health check endpoint."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_returns_200(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_contains_agent_info(self, client: TestClient):
        response = client.get("/health")
        data = response.json()
        assert "agent" in data
        assert "tools" in data
        assert data["agent"] == "agentic-workflow"
        assert data["tools"] == ["mock_tool"]
