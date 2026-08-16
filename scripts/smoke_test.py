"""Local smoke test - verifies core imports and basic functionality without GCP."""
from agentic_workflow.core.interfaces import (
    AgentConfig,
    AgentResponse,
    IAgent,
    IMemory,
    ITool,
    IToolRegistry,
    Message,
    MessageRole,
    ToolCall,
    ToolCallStatus,
)
from agentic_workflow.core.registry import InMemoryToolRegistry


def test_interfaces_importable():
    """Verify all core interfaces are importable."""
    assert IAgent
    assert ITool
    assert IMemory
    assert IToolRegistry
    print("✓ All interfaces importable")


def test_message_creation():
    """Test message data model."""
    msg = Message(role=MessageRole.USER, content="Hello, agent!")
    assert msg.role == MessageRole.USER
    assert msg.content == "Hello, agent!"
    assert msg.metadata == {}
    assert msg.tool_calls == []
    print("✓ Message creation works")


def test_tool_call_creation():
    """Test tool call data model."""
    tc = ToolCall(
        id="call_123",
        name="test_tool",
        arguments={"key": "value"},
    )
    assert tc.status == ToolCallStatus.PENDING
    assert tc.result is None
    assert tc.error is None
    print("✓ Tool call creation works")


def test_agent_response_creation():
    """Test agent response data model."""
    resp = AgentResponse(
        message="Here is the result",
        tool_calls=[ToolCall(id="1", name="tool1", arguments={})],
        finish_reason="stop",
        usage={"prompt_tokens": 10, "completion_tokens": 20},
    )
    assert resp.message == "Here is the result"
    assert len(resp.tool_calls) == 1
    assert resp.usage["prompt_tokens"] == 10
    print("✓ Agent response creation works")


def test_agent_config():
    """Test agent configuration."""
    config = AgentConfig(
        name="test-agent",
        model="gemini-2.5-flash",
        system_prompt="You are helpful.",
        temperature=0.5,
        max_tokens=4096,
        tools=["tool1", "tool2"],
    )
    assert config.name == "test-agent"
    assert config.model == "gemini-2.5-flash"
    assert config.tools == ["tool1", "tool2"]
    print("✓ Agent config works")


def test_tool_registry():
    """Test in-memory tool registry."""
    registry = InMemoryToolRegistry()

    # Test empty registry
    assert registry.list_tools() == []
    assert registry.get("nonexistent") is None

    # Test registration
    class DummyTool(ITool):
        @property
        def name(self) -> str:
            return "dummy"

        @property
        def description(self) -> str:
            return "A dummy tool"

        def schema(self) -> dict:
            return {}

        async def execute(self, arguments: dict) -> str:
            return "dummy result"

    tool = DummyTool()
    registry.register(tool)
    assert "dummy" in registry.list_tools()
    assert registry.get("dummy") is tool
    print("✓ Tool registry works")


def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("AgenticWorkflow - Local Smoke Test")
    print("=" * 60)

    tests = [
        test_interfaces_importable,
        test_message_creation,
        test_tool_call_creation,
        test_agent_response_creation,
        test_agent_config,
        test_tool_registry,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        exit(1)


if __name__ == "__main__":
    main()
