"""Integration tests for the agentic workflow platform.

These tests verify the full request/response flow WITHOUT deploying to GCP.
They use:
- FastAPI TestClient for HTTP layer
- Mock ADK agent responses
- In-memory Firestore substitute
- Local mock MCP server
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agentic_workflow.core.interfaces import (
    AgentConfig,
    AgentResponse,
    IAgent,
    IMemory,
    ITool,
    Message,
    MessageRole,
    ToolCall,
    ToolCallStatus,
)
from agentic_workflow.core.registry import InMemoryToolRegistry
from agentic_workflow.mcp.manager import MCPToolManager


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_agent() -> IAgent:
    """Create a mock agent that returns predictable responses."""

    class MockIntegrationAgent(IAgent):
        async def invoke(self, messages, config=None):
            last_msg = messages[-1].content if messages else ""
            return AgentResponse(
                message=f"Mock response to: {last_msg}",
                tool_calls=[],
                usage={"prompt_tokens": 10, "completion_tokens": 20},
            )

        async def stream(self, messages, config=None):
            yield "Mock stream response"

        def register_tool(self, tool: ITool) -> None:
            pass

        def list_tools(self) -> list[str]:
            return ["mock_tool"]

    return MockIntegrationAgent()


@pytest.fixture
def mock_memory() -> IMemory:
    """Create an in-memory mock for FirestoreMemory."""

    class MockIntegrationMemory(IMemory):
        def __init__(self) -> None:
            self._sessions: dict[str, list[Message]] = {}

        async def get_session(self, session_id: str):
            return self._sessions.get(session_id)

        async def save_session(self, session_id: str, messages, ttl=None):
            self._sessions[session_id] = list(messages)

        async def delete_session(self, session_id: str) -> None:
            self._sessions.pop(session_id, None)

        async def search(self, query: str, limit=10, session_id=None):
            return []

    return MockIntegrationMemory()


@pytest.fixture
def mock_mcp_manager() -> MCPToolManager:
    """Create an MCP manager with a mock remote server."""
    manager = MCPToolManager()
    return manager


@pytest.fixture
def client(mock_agent: IAgent, mock_memory: IMemory, mock_mcp_manager: MCPToolManager):
    """Create a FastAPI TestClient with mocked dependencies."""
    from agentic_workflow.api.server import FastAPI, lifespan

    # Patch the globals before app startup
    with patch("agentic_workflow.api.server.registry") as mock_registry, patch(
        "agentic_workflow.api.server.memory"
    ) as mock_mem, patch("agentic_workflow.api.server.agent") as mock_agt:

        mock_registry.list.return_value = ["mock_tool"]
        mock_registry.get.return_value = MagicMock()
        mock_registry.discover = AsyncMock(return_value=[])
        mock_mem.get_session = AsyncMock(return_value=None)
        mock_mem.save_session = AsyncMock()
        mock_mem.delete_session = AsyncMock()
        mock_agt.invoke = AsyncMock(
            return_value=AgentResponse(
                message="Integration test response",
                tool_calls=[],
                usage={"prompt_tokens": 10, "completion_tokens": 20},
            )
        )
        mock_agt.config.name = "test-agent"
        mock_agt.config.model = "gemini-2.5-flash"

        # Create test app
        test_app = FastAPI(lifespan=lifespan)

        # Copy routes from main app
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

        with TestClient(test_app) as client:
            yield client


# =============================================================================
# Health & Basic API Tests
# =============================================================================


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


# =============================================================================
# Chat Flow Integration Tests
# =============================================================================


class TestChatFlow:
    """Test the complete chat request/response flow."""

    def test_chat_returns_response(self, client: TestClient):
        response = client.post(
            "/chat",
            json={"message": "Hello, agent!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "session_id" in data

    def test_chat_with_session_id(self, client: TestClient):
        response = client.post(
            "/chat",
            json={"message": "First message", "session_id": "test-session-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"

    def test_chat_empty_message_fails(self, client: TestClient):
        response = client.post("/chat", json={"message": ""})
        assert response.status_code == 422  # Validation error

    def test_chat_with_tools_filter(self, client: TestClient):
        response = client.post(
            "/chat",
            json={"message": "Use tools", "tools": ["tool1", "tool2"]},
        )
        assert response.status_code == 200

    def test_chat_stream_endpoint(self, client: TestClient):
        response = client.post(
            "/chat/stream",
            json={"message": "Stream this"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


# =============================================================================
# Tool Registration Integration Tests
# =============================================================================


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
        response = client.post(
            "/tools/register",
            json={"source": "invalid-source"},
        )
        assert response.status_code == 400


# =============================================================================
# Session Management Integration Tests
# =============================================================================


class TestSessionManagement:
    """Test session creation, retrieval, and deletion."""

    def test_delete_nonexistent_session(self, client: TestClient):
        response = client.delete("/sessions/nonexistent-session")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"


# =============================================================================
# MCP Manager Integration Tests
# =============================================================================


class TestMCPManagerIntegration:
    """Test MCP tool discovery with local mock server."""

    @pytest.mark.asyncio
    async def test_discover_remote_tools(self):
        """Test discovering tools from a mock remote MCP server."""
        manager = MCPToolManager()

        # Create a mock FastMCP client
        mock_tool = MagicMock()
        mock_tool.name = "remote_test_tool"
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object", "properties": {"arg": {"type": "string"}}}

        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[mock_tool])
        mock_client.call_tool = AsyncMock(return_value="tool result")

        with patch("agentic_workflow.mcp.manager.Client") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            tools = await manager.discover_remote("https://example.com/mcp")
            assert len(tools) == 1
            assert tools[0].name == "remote_test_tool"

    @pytest.mark.asyncio
    async def test_discover_local_tools(self):
        """Test discovering tools from a local MCP server."""
        manager = MCPToolManager()

        mock_tool = MagicMock()
        mock_tool.name = "local_test_tool"
        mock_tool.description = "A local test tool"
        mock_tool.inputSchema = {"type": "object"}

        mock_server = AsyncMock()
        mock_server.list_tools = AsyncMock(return_value=[mock_tool])

        with patch("agentic_workflow.mcp.manager.FastMCP") as MockFastMCP:
            MockFastMCP.return_value = mock_server

            tools = await manager.discover_local("test_module")
            assert len(tools) == 1
            assert tools[0].name == "local_test_tool"

    @pytest.mark.asyncio
    async def test_invalid_source_raises_error(self):
        manager = MCPToolManager()
        with pytest.raises(ValueError, match="Unsupported tool source format"):
            await manager.discover("invalid-source")


# =============================================================================
# Memory Integration Tests
# =============================================================================


class TestMemoryIntegration:
    """Test memory operations with mock Firestore."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_session(self):
        """Test saving and retrieving a conversation session."""

        class MockFirestoreMemory(IMemory):
            def __init__(self) -> None:
                self._sessions: dict[str, list[Message]] = {}

            async def get_session(self, session_id: str):
                return self._sessions.get(session_id)

            async def save_session(self, session_id: str, messages, ttl=None):
                self._sessions[session_id] = list(messages)

            async def delete_session(self, session_id: str) -> None:
                self._sessions.pop(session_id, None)

            async def search(self, query: str, limit=10, session_id=None):
                return []

        memory = MockFirestoreMemory()

        messages = [
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi there!"),
        ]

        # Test via the interface
        await memory.save_session("session-1", messages)
        result = await memory.get_session("session-1")
        assert result is not None
        assert len(result) == 2
        assert result[0].content == "Hello"
        assert result[1].content == "Hi there!"

    @pytest.mark.asyncio
    async def test_search_across_sessions(self):
        """Test searching for messages across sessions."""

        class MockSearchMemory(IMemory):
            def __init__(self) -> None:
                self._sessions: dict[str, list[Message]] = {
                    "s1": [Message(role=MessageRole.USER, content="Python question")],
                    "s2": [Message(role=MessageRole.USER, content="Java question")],
                }

            async def get_session(self, session_id: str):
                return self._sessions.get(session_id)

            async def save_session(self, session_id: str, messages, ttl=None):
                self._sessions[session_id] = list(messages)

            async def delete_session(self, session_id: str) -> None:
                self._sessions.pop(session_id, None)

            async def search(self, query: str, limit=10, session_id=None):
                results = []
                for msgs in self._sessions.values():
                    for msg in msgs:
                        if query.lower() in msg.content.lower():
                            results.append(msg)
                return results[:limit]

        memory = MockSearchMemory()
        results = await memory.search("Python")
        assert len(results) == 1
        assert results[0].content == "Python question"


# =============================================================================
# Agent Framework Swap Tests
# =============================================================================


class TestFrameworkSwap:
    """Test that the framework-agnostic interface works."""

    def test_agent_interface_contract(self):
        """Verify any framework implementation satisfies IAgent."""

        class MinimalAgent(IAgent):
            async def invoke(self, messages, config=None):
                return AgentResponse(message="minimal")

            async def stream(self, messages, config=None):
                yield "minimal"

            def register_tool(self, tool: ITool) -> None:
                pass

            def list_tools(self) -> list[str]:
                return []

        agent = MinimalAgent()
        assert agent.list_tools() == []

    def test_memory_interface_contract(self):
        """Verify any memory implementation satisfies IMemory."""

        class MinimalMemory(IMemory):
            async def get_session(self, session_id: str):
                return None

            async def save_session(self, session_id: str, messages, ttl=None):
                pass

            async def delete_session(self, session_id: str) -> None:
                pass

            async def search(self, query: str, limit=10, session_id=None):
                return []

        memory = MinimalMemory()
        assert memory is not None

    def test_tool_interface_contract(self):
        """Verify any tool implementation satisfies ITool."""

        class MinimalTool(ITool):
            @property
            def name(self) -> str:
                return "minimal"

            @property
            def description(self) -> str:
                return "Minimal tool"

            def schema(self) -> dict[str, Any]:
                return {}

            async def execute(self, arguments: dict[str, Any]) -> str:
                return "minimal result"

        tool = MinimalTool()
        assert tool.name == "minimal"
        assert tool.description == "Minimal tool"


# =============================================================================
# End-to-End Flow Tests
# =============================================================================


class TestEndToEndFlow:
    """Test complete user journeys through the API."""

    def test_full_conversation_flow(self, client: TestClient):
        """Test a complete conversation: send message, verify response."""
        session_id = "integration-test-session"

        response = client.post(
            "/chat",
            json={
                "message": "What is the capital of France?",
                "session_id": session_id,
                "user_id": "test-user",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"]
        assert data["session_id"] == session_id

    def test_multi_turn_conversation(self, client: TestClient):
        """Test that session context is maintained across turns."""
        session_id = "multi-turn-session"

        # First turn
        client.post("/chat", json={"message": "My name is Alice", "session_id": session_id})

        # Second turn
        response = client.post(
            "/chat",
            json={"message": "What is my name?", "session_id": session_id},
        )
        assert response.status_code == 200

    def test_concurrent_requests(self, client: TestClient):
        """Test that the API handles concurrent requests."""
        import threading

        results = []

        def make_request(idx: int):
            try:
                resp = client.post(
                    "/chat",
                    json={"message": f"Request {idx}", "session_id": f"session-{idx}"},
                )
                results.append((idx, resp.status_code))
            except Exception as e:
                results.append((idx, str(e)))

        threads = [threading.Thread(target=make_request, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        for idx, status in results:
            assert status == 200
