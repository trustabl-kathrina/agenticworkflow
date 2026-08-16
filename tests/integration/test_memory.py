"""Integration tests for memory operations."""
from __future__ import annotations

import pytest

from agentic_workflow.core.interfaces import IMemory, Message, MessageRole


class TestMemoryIntegration:
    """Test memory operations with in-memory mock."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_session(self):
        class MockMemory(IMemory):
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

        memory = MockMemory()
        messages = [
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi there!"),
        ]

        await memory.save_session("session-1", messages)
        result = await memory.get_session("session-1")
        assert result is not None
        assert len(result) == 2
        assert result[0].content == "Hello"
        assert result[1].content == "Hi there!"

    @pytest.mark.asyncio
    async def test_search_across_sessions(self):
        class SearchMemory(IMemory):
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

        memory = SearchMemory()
        results = await memory.search("Python")
        assert len(results) == 1
        assert results[0].content == "Python question"
