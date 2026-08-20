"""Integration tests for the chat endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestChatFlow:
    """Test the complete chat request/response flow."""

    def test_chat_returns_response(self, client: TestClient):
        response = client.post(
            "/chat",
            json={"message": "Hello, agent!"},
            headers={"X-API-Key": "test-master-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "session_id" in data

    def test_chat_with_session_id(self, client: TestClient):
        response = client.post(
            "/chat",
            json={"message": "First message", "session_id": "test-session-123"},
            headers={"X-API-Key": "test-master-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"

    def test_chat_empty_message_fails(self, client: TestClient):
        response = client.post(
            "/chat",
            json={"message": ""},
            headers={"X-API-Key": "test-master-key"},
        )
        assert response.status_code == 422

    def test_chat_with_tools_filter(self, client: TestClient):
        response = client.post(
            "/chat",
            json={"message": "Use tools", "tools": ["tool1", "tool2"]},
            headers={"X-API-Key": "test-master-key"},
        )
        assert response.status_code == 200

    def test_chat_stream_endpoint(self, client: TestClient):
        response = client.post(
            "/chat/stream",
            json={"message": "Stream this"},
            headers={"X-API-Key": "test-master-key"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
