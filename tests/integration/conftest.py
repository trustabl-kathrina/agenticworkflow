"""Shared fixtures for integration tests."""
from __future__ import annotations

from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentic_workflow.agents.adk_agent import AgentConfig
from agentic_workflow.core.interfaces import AgentResponse, MessageRole


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
    mock.list.return_value = ["mock_tool"]
    mock.get.return_value = MagicMock()
    mock.discover = AsyncMock(return_value=[])
    mock.register = MagicMock()
    return mock


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI app with routes copied from the main app."""
    test_app = FastAPI()

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
    """Create TestClient with module globals patched."""
    with patch("agentic_workflow.api.server.agent", mock_agent), \
         patch("agentic_workflow.api.server.memory", mock_memory), \
         patch("agentic_workflow.api.server.registry", mock_registry):
        with TestClient(app) as test_client:
            yield test_client
