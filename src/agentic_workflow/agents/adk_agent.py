"""
ADK-based agent implementation.

This wraps Google's Agent Development Kit (ADK) behind the framework-agnostic
IAgent interface. To swap to LangGraph or another framework, create a new
implementation of IAgent without changing any application code.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Sequence
from typing import Any

from agentic_workflow.core.interfaces import (
    AgentConfig,
    AgentResponse,
    IAgent,
    ITool,
    Message,
    ToolCall,
)
from agentic_workflow.core.registry import InMemoryToolRegistry

logger = logging.getLogger(__name__)


class ADKAgent(IAgent):
    """
    Agent implementation using Google's Agent Development Kit.

    This class wraps ADK's Agent to conform to the IAgent interface.
    All ADK-specific details are contained here.
    """

    INVOKE_TIMEOUT_SECONDS = 60

    def __init__(
        self,
        config: AgentConfig,
        registry: InMemoryToolRegistry | None = None,
    ) -> None:
        self.config = config
        self._registry = registry or InMemoryToolRegistry()
        self._agent: Any = None
        self._runner: Any = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Lazy initialization of the ADK agent."""
        if self._initialized:
            return

        try:
            from google.adk.agents import Agent
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService

            tools = []
            for tool_name in self.config.tools:
                tool = self._registry.get(tool_name)
                if tool:
                    tools.append(self._wrap_tool(tool))

            self._agent = Agent(
                name=self.config.name,
                model=self.config.model,
                instruction=self.config.system_prompt or "You are a helpful assistant.",
                tools=tools,
            )

            session_service = InMemorySessionService()
            self._runner = Runner(
                agent=self._agent,
                app_name=self.config.name,
                session_service=session_service,
            )
            self._initialized = True
            logger.info(
                f"ADK agent '{self.config.name}' initialized with model {self.config.model}"
            )

        except ImportError as e:
            raise ImportError(
                "Google ADK is required for ADKAgent. "
                "Install it with: pip install google-adk google-genai"
            ) from e

    def _wrap_tool(self, tool: ITool) -> Any:
        """Convert an ITool to an ADK-compatible tool."""
        try:
            from google.adk.tools import FunctionTool  # type: ignore[attr-defined]

            async def _adk_tool_func(**kwargs: Any) -> str:
                return await tool.execute(kwargs)

            return FunctionTool(  # type: ignore[call-arg]
                func=_adk_tool_func,
                name=tool.name,
                description=tool.description,
            )
        except ImportError:
            logger.warning(f"ADK not available, tool '{tool.name}' will not be wrapped")
            return None

    async def invoke(
        self,
        messages: Sequence[Message],
        config: AgentConfig | None = None,
    ) -> AgentResponse:
        """Process messages and return a response."""
        await self._ensure_initialized()

        effective_config = config or self.config
        session_id = effective_config.metadata.get("session_id", "default")
        user_id = effective_config.metadata.get("user_id", "user")

        last_message = messages[-1] if messages else None
        if not last_message:
            return AgentResponse(message="No input provided.")

        try:
            from google.genai import types

            content = types.Content(
                role=last_message.role.value,
                parts=[types.Part(text=last_message.content)],
            )

            events = []
            async with asyncio.timeout(ADKAgent.INVOKE_TIMEOUT_SECONDS):
                async for event in self._runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content,
                ):
                    events.append(event)

            response_text = ""
            tool_calls = []
            usage = {}

            for event in events:
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            response_text += part.text

                if hasattr(event, "tool_calls"):
                    for tc in event.tool_calls:
                        tool_calls.append(
                            ToolCall(
                                id=getattr(tc, "id", ""),
                                name=getattr(tc, "name", ""),
                                arguments=getattr(tc, "args", {}),
                            )
                        )

                if hasattr(event, "usage_metadata"):
                    usage = {
                        "prompt_tokens": getattr(
                            event.usage_metadata, "prompt_token_count", 0
                        ),
                        "completion_tokens": getattr(
                            event.usage_metadata, "candidates_token_count", 0
                        ),
                    }

            return AgentResponse(
                message=response_text or "No response generated.",
                tool_calls=tool_calls,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"Agent invocation failed: {e}", exc_info=True)
            return AgentResponse(
                message=f"Error: {e!s}",
                finish_reason="error",
            )

    async def stream(  # type: ignore[override]
        self,
        messages: Sequence[Message],
        config: AgentConfig | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream responses for real-time interaction."""
        await self._ensure_initialized()

        effective_config = config or self.config
        session_id = effective_config.metadata.get("session_id", "default")
        user_id = effective_config.metadata.get("user_id", "user")

        last_message = messages[-1] if messages else None
        if not last_message:
            yield "No input provided."
            return

        try:
            from google.genai import types

            content = types.Content(
                role=last_message.role.value,
                parts=[types.Part(text=last_message.content)],
            )

            async with asyncio.timeout(ADKAgent.INVOKE_TIMEOUT_SECONDS):
                async for event in self._runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=content,
                ):
                    if hasattr(event, "content") and event.content:
                        for part in event.content.parts:
                            if hasattr(part, "text") and part.text:
                                yield part.text

        except TimeoutError:
            logger.error("Agent stream timed out")
            yield "Error: Response timed out"
        except Exception as e:
            logger.error(f"Agent stream failed: {e}", exc_info=True)
            yield f"Error: {e!s}"

    def register_tool(self, tool: ITool) -> None:
        """Register a tool with the agent."""
        self._registry.register(tool)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return self._registry.list_tools()
