"""Tests for core interfaces and registry."""

from __future__ import annotations

import pytest

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


class MockTool(ITool):
    """Mock tool for testing."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    def schema(self) -> dict[str, object]:
        return {"type": "object", "properties": {"arg": {"type": "string"}}}

    async def execute(self, arguments: dict[str, object]) -> str:
        return f"mock result for {arguments}"


class MockMemory(IMemory):
    """Mock memory for testing."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[Message]] = {}

    async def get_session(self, session_id: str) -> list[Message] | None:
        return self._sessions.get(session_id)

    async def save_session(
        self,
        session_id: str,
        messages: list[Message],
        ttl: int | None = None,
    ) -> None:
        self._sessions[session_id] = list(messages)

    async def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def search(
        self,
        query: str,
        limit: int = 10,
        session_id: str | None = None,
    ) -> list[Message]:
        return []


class MockAgent(IAgent):
    """Mock agent for testing."""

    def __init__(self) -> None:
        self.tools: list[ITool] = []

    async def invoke(
        self,
        messages: list[Message],
        config: AgentConfig | None = None,
    ) -> AgentResponse:
        return AgentResponse(message="mock response", tool_calls=[])

    async def stream(
        self,
        messages: list[Message],
        config: AgentConfig | None = None,
    ) -> object:
        yield "mock stream"

    def register_tool(self, tool: ITool) -> None:
        self.tools.append(tool)

    def list_tools(self) -> list[str]:
        return [t.name for t in self.tools]


class TestInterfaces:
    """Test core data models."""

    def test_message_creation(self) -> None:
        msg = Message(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"

    def test_tool_call_creation(self) -> None:
        tc = ToolCall(id="1", name="test", arguments={"a": 1})
        assert tc.status == ToolCallStatus.PENDING
        assert tc.result is None

    def test_agent_response_creation(self) -> None:
        resp = AgentResponse(message="test", usage={"prompt_tokens": 10})
        assert resp.message == "test"
        assert resp.usage["prompt_tokens"] == 10

    def test_agent_config_defaults(self) -> None:
        config = AgentConfig(name="test", model="gemini-2.5-flash")
        assert config.temperature == 0.7
        assert config.max_tokens == 8192
        assert config.tools == []


class TestMockAgent:
    """Test agent interface contract."""

    @pytest.mark.asyncio
    async def test_invoke_returns_response(self) -> None:
        agent = MockAgent()
        messages = [Message(role=MessageRole.USER, content="Hi")]
        resp = await agent.invoke(messages)
        assert isinstance(resp, AgentResponse)
        assert resp.message == "mock response"

    @pytest.mark.asyncio
    async def test_stream_returns_chunks(self) -> None:
        agent = MockAgent()
        messages = [Message(role=MessageRole.USER, content="Hi")]
        chunks = []
        async for chunk in agent.stream(messages):
            chunks.append(chunk)
        assert chunks == ["mock stream"]

    def test_register_and_list_tools(self) -> None:
        agent = MockAgent()
        tool = MockTool()
        agent.register_tool(tool)
        assert "mock_tool" in agent.list_tools()


class TestMockMemory:
    """Test memory interface contract."""

    @pytest.mark.asyncio
    async def test_save_and_get_session(self) -> None:
        memory = MockMemory()
        msgs = [Message(role=MessageRole.USER, content="Hello")]
        await memory.save_session("s1", msgs)
        result = await memory.get_session("s1")
        assert result is not None
        assert len(result) == 1
        assert result[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_delete_session(self) -> None:
        memory = MockMemory()
        msgs = [Message(role=MessageRole.USER, content="Hello")]
        await memory.save_session("s1", msgs)
        await memory.delete_session("s1")
        assert await memory.get_session("s1") is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self) -> None:
        memory = MockMemory()
        assert await memory.get_session("nonexistent") is None
