"""
Core abstraction interfaces for the agentic workflow platform.

These protocols define framework-agnostic contracts that any agent framework
(ADK, LangGraph, CrewAI, etc.) can implement. This allows swapping frameworks
without changing application code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MessageRole(StrEnum):
    """Standard message roles in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ToolCallStatus(StrEnum):
    """Status of a tool execution."""

    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class Message:
    """A single message in a conversation."""

    role: MessageRole
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class ToolCall:
    """Represents a tool invocation request or result."""

    id: str
    name: str
    arguments: dict[str, Any]
    result: str | None = None
    status: ToolCallStatus = ToolCallStatus.PENDING
    error: str | None = None


@dataclass
class AgentResponse:
    """Standard response from any agent implementation."""

    message: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Configuration for an agent instance."""

    name: str
    model: str
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int = 8192
    max_iterations: int = 10
    tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class IAgent(ABC):
    """
    Framework-agnostic agent interface.

    Any agent framework (ADK, LangGraph, etc.) implements this interface
    to provide a consistent API to the rest of the application.
    """

    @abstractmethod
    async def invoke(
        self,
        messages: Sequence[Message],
        config: AgentConfig | None = None,
    ) -> AgentResponse:
        """Process messages and return a response."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: Sequence[Message],
        config: AgentConfig | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream responses for real-time interaction."""
        ...

    @abstractmethod
    def register_tool(self, tool: ITool) -> None:
        """Register a tool with the agent."""
        ...

    @abstractmethod
    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        ...


class ITool(ABC):
    """
    Framework-agnostic tool interface.

    Tools can be local functions, remote MCP servers, or any executable
    capability. Implementations wrap framework-specific tool definitions.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        ...

    @property
    @abstractmethod
    def schema(self) -> dict[str, Any]:
        """JSON Schema for the tool's parameters."""
        ...

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> str:
        """Execute the tool with given arguments."""
        ...


class IMemory(ABC):
    """
    Framework-agnostic memory interface.

    Implementations can use Firestore, Redis, Vertex AI Memory Bank,
    or any persistence backend.
    """

    @abstractmethod
    async def get_session(self, session_id: str) -> list[Message] | None:
        """Retrieve messages for a session."""
        ...

    @abstractmethod
    async def save_session(
        self, session_id: str, messages: Sequence[Message], ttl: int | None = None
    ) -> None:
        """Persist messages for a session."""
        ...

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        ...

    @abstractmethod
    async def search(
        self, query: str, limit: int = 10, session_id: str | None = None
    ) -> list[Message]:
        """Search across sessions (for long-term memory)."""
        ...


class IToolRegistry(ABC):
    """
    Registry for discovering and managing tools.

    Enables dynamic tool loading from MCP servers, plugins, or modules
    without changing agent code.
    """

    @abstractmethod
    def register(self, tool: ITool) -> None:
        """Register a tool."""
        ...

    @abstractmethod
    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        ...

    @abstractmethod
    def get(self, name: str) -> ITool | None:
        """Get a tool by name."""
        ...

    @abstractmethod
    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        ...

    @abstractmethod
    async def discover(self, source: str) -> list[ITool]:
        """Discover tools from an external source (MCP server, plugin, etc.)."""
        ...
