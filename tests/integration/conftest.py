"""Shared fixtures for integration tests."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from agentic_workflow.core.interfaces import AgentResponse


@pytest.fixture(scope="session")
def mock_agent() -> MagicMock:
    mock = MagicMock()
    mock.config.name = "test-agent"
    mock.config.model = "gemini-2.5-flash"
    mock.invoke = AsyncMock(
        return_value=AgentResponse(
            message="Mock response",
            tool_calls=[],
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            finish_reason="stop",
        )
    )

    async def _stream_iter(*args, **kwargs):
        yield "Mock stream chunk"

    mock.stream = _stream_iter
    return mock


@pytest.fixture(scope="session")
def mock_memory() -> MagicMock:
    mock = MagicMock()
    mock.get_session = AsyncMock(return_value=None)
    mock.save_session = AsyncMock()
    mock.delete_session = AsyncMock()
    mock.search = AsyncMock(return_value=[])
    return mock


@pytest.fixture(scope="session")
def mock_registry() -> MagicMock:
    mock = MagicMock()
    mock.list_tools.return_value = ["mock_tool"]
    mock.get.return_value = MagicMock()
    mock.discover = AsyncMock(return_value=[])
    mock.register = MagicMock()
    return mock


class _FakeAPIMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.device_id = "test-device"
        return await call_next(request)


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI app with routes copied from the main app."""
    os.environ.setdefault("API_KEY", "test-master-key")

    test_app = FastAPI()
    test_app.add_middleware(_FakeAPIMiddleware)

    from agentic_workflow.api.server import (
        chat,
        chat_stream,
        delete_session,
        health,
        invoke_tool,
        list_tools,
        register_tool,
    )

    test_app.get("/health")(health)
    test_app.post("/chat")(chat)
    test_app.post("/chat/stream")(chat_stream)
    test_app.post("/tools/register")(register_tool)
    test_app.get("/tools")(list_tools)
    test_app.post("/tools/{tool_name}/invoke")(invoke_tool)
    test_app.delete("/sessions/{session_id}")(delete_session)

    return test_app


@pytest.fixture
def client(app: FastAPI, mock_agent, mock_memory, mock_registry) -> TestClient:
    """Create TestClient with module-level app.state set to mocks."""
    from agentic_workflow.api.server import app as server_app

    server_app.state.registry = mock_registry
    server_app.state.memory = mock_memory
    server_app.state.agent = mock_agent
    with TestClient(app) as test_client:
        yield test_client
