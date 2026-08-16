"""Integration tests for framework-agnostic interface contracts."""
from __future__ import annotations

from typing import Any

from agentic_workflow.core.interfaces import (
    AgentResponse,
    IAgent,
    IMemory,
    ITool,
)


class TestFrameworkSwap:
    """Test that the framework-agnostic interface works."""

    def test_agent_interface_contract(self):
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
