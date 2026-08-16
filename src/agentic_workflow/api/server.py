"""
FastAPI application server for the agentic workflow.

This server exposes the agent as an HTTP API and handles:
- Request routing to the agent
- Session management via Memory
- Tool discovery and registration
- Health checks and metrics
"""
from __future__ import annotations

import os
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from agentic_workflow.agents.adk_agent import ADKAgent, AgentConfig  # type: ignore[attr-defined]
from agentic_workflow.core.interfaces import Message, MessageRole
from agentic_workflow.core.registry import InMemoryToolRegistry
from agentic_workflow.memory.firestore_memory import FirestoreMemory

# Configure structlog for Cloud Logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Global state (in production, use proper dependency injection)
registry: InMemoryToolRegistry | None = None
memory: FirestoreMemory | None = None
agent: ADKAgent | None = None


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID and timing to each request."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        request_id = str(uuid.uuid4())
        start_time = time.time()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "request_processed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        response.headers["X-Request-ID"] = request_id
        return response


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce API key authentication."""

    def __init__(self, app: Any, api_key: str | None = None) -> None:
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.url.path == "/health":
            return await call_next(request)

        if not self.api_key:
            return await call_next(request)

        client_key = request.headers.get("X-API-Key")
        if not client_key or client_key != self.api_key:
            logger.warning(
                "unauthorized_request",
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown",
            )
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    global registry, memory, agent

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    region = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west3")

    registry = InMemoryToolRegistry()
    memory = FirestoreMemory(project_id=project_id or "local-dev")
    agent = ADKAgent(
        config=AgentConfig(
            name="agentic-workflow",
            model=os.getenv("AGENT_MODEL", "gemini-2.5-flash"),
            system_prompt=os.getenv("AGENT_SYSTEM_PROMPT"),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "8192")),
        ),
        registry=registry,
    )

    logger.info("Agentic Workflow server started", project=project_id, region=region)
    yield
    logger.info("Agentic Workflow server shutting down")


app = FastAPI(
    title="Agentic Workflow API",
    description="Extensible AI agent platform with framework-agnostic architecture",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(..., min_length=1, description="User message")
    session_id: str = Field(default="default", description="Conversation session ID")
    user_id: str = Field(default="user", description="User identifier")
    tools: list[str] = Field(default_factory=list, description="Tools to enable")
    stream: bool = Field(default=False, description="Enable streaming response")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    message: str
    session_id: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = Field(default_factory=dict)


class ToolRegistrationRequest(BaseModel):
    """Request to register a new tool."""

    source: str = Field(..., description="MCP server URL or local module path")
    name: str | None = Field(default=None, description="Optional custom name")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    agent: str
    tools: list[str]


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        agent=agent.config.name if agent else "not initialized",
        tools=registry.list_tools() if registry else [],
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint.

    Accepts a user message and returns the agent's response.
    Maintains conversation context via session_id.
    """
    if not agent or not memory:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    session_id = request.session_id
    user_id = request.user_id

    # Load existing session history
    history = await memory.get_session(session_id) or []

    # Build message list
    messages = list(history)
    messages.append(
        Message(
            role=MessageRole.USER,
            content=request.message,
            metadata={"user_id": user_id},
        )
    )

    # Configure agent for this request
    config = AgentConfig(
        name=agent.config.name,
        model=agent.config.model,
        system_prompt=agent.config.system_prompt,
        temperature=agent.config.temperature,
        max_tokens=agent.config.max_tokens,
        tools=request.tools or agent.config.tools,
        metadata={"session_id": session_id, "user_id": user_id},
    )

    # Invoke agent
    start_time = time.time()
    response = await agent.invoke(messages, config)
    latency_ms = (time.time() - start_time) * 1000

    logger.info(
        "agent_invocation_completed",
        session_id=session_id,
        user_id=user_id,
        model=config.model,
        latency_ms=round(latency_ms, 2),
        tool_calls_count=len(response.tool_calls),
        finish_reason=response.finish_reason,
        usage=response.usage,
    )

    # Save updated history
    messages.append(
        Message(
            role=MessageRole.ASSISTANT,
            content=response.message,
            metadata={"tool_calls": response.tool_calls},
        )
    )
    await memory.save_session(session_id, messages)

    if response.finish_reason == "error":
        logger.error(
            "agent_invocation_failed",
            session_id=session_id,
            user_id=user_id,
            error=response.message,
        )

    return ChatResponse(
        message=response.message,
        session_id=session_id,
        tool_calls=[tc.__dict__ for tc in response.tool_calls],
        finish_reason=response.finish_reason,
        usage=response.usage,
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Streaming chat endpoint for real-time responses."""
    if not agent or not memory:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    session_id = request.session_id
    user_id = request.user_id
    history = await memory.get_session(session_id) or []

    messages = list(history)
    messages.append(
        Message(
            role=MessageRole.USER,
            content=request.message,
            metadata={"user_id": user_id},
        )
    )

    config = AgentConfig(
        name=agent.config.name,
        model=agent.config.model,
        system_prompt=agent.config.system_prompt,
        temperature=agent.config.temperature,
        max_tokens=agent.config.max_tokens,
        tools=request.tools or agent.config.tools,
        metadata={"session_id": session_id, "user_id": user_id},
    )

    async def generate() -> AsyncGenerator[str, None]:
        full_response = ""
        async for chunk in agent.stream(messages, config):
            full_response += chunk
            yield f"data: {chunk}\n\n"

        # Save session after streaming completes
        messages.append(
            Message(
                role=MessageRole.ASSISTANT,
                content=full_response,
            )
        )
        await memory.save_session(session_id, messages)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/tools/register")
async def register_tool(request: ToolRegistrationRequest) -> dict[str, Any]:
    """Register a new MCP tool dynamically."""
    if not registry:
        raise HTTPException(status_code=503, detail="Registry not initialized")

    try:
        tools = await registry.discover(request.source)
        registered = []
        for tool in tools:
            registry.register(tool)
            registered.append(tool.name)

        return {
            "status": "success",
            "registered": registered,
            "count": len(registered),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tools", response_model=list[str])
async def list_tools() -> list[str]:
    """List all registered tools."""
    if not registry:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return registry.list_tools()


@app.post("/tools/{tool_name}/invoke")
async def invoke_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a tool directly."""
    if not registry:
        raise HTTPException(status_code=503, detail="Registry not initialized")

    tool = registry.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    try:
        result = await tool.execute(arguments)
        return {"tool": tool_name, "result": result, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete a conversation session."""
    if not memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")

    await memory.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}
