"""Integration tests for session management."""
from __future__ import annotations

from fastapi.testclient import TestClient


class TestSessionManagement:
    """Test session creation, retrieval, and deletion."""

    def test_delete_nonexistent_session(self, client: TestClient):
        response = client.delete(
            "/sessions/nonexistent-session",
            headers={"X-API-Key": "test-master-key"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
