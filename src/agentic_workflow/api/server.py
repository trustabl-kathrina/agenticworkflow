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
import secrets
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from agentic_workflow.agents.adk_agent import ADKAgent
from agentic_workflow.core.interfaces import AgentConfig, Message, MessageRole
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


def get_registry() -> InMemoryToolRegistry:
    """Dependency: get the tool registry."""
    return cast(InMemoryToolRegistry, app.state.registry)


def get_memory() -> FirestoreMemory:
    """Dependency: get the memory backend."""
    return cast(FirestoreMemory, app.state.memory)


def get_agent() -> ADKAgent:
    """Dependency: get the agent."""
    return cast(ADKAgent, app.state.agent)


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

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.url.path == "/health":
            return await call_next(request)

        api_key = os.getenv("API_KEY")
        if not api_key:
            logger.warning(
                "auth_failed",
                reason="API_KEY not configured",
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown",
            )
            raise HTTPException(status_code=401, detail="Authentication failed")

        client_key = request.headers.get("X-API-Key")
        if not client_key or not secrets.compare_digest(client_key, api_key):
            logger.warning(
                "auth_failed",
                reason="invalid_api_key",
                path=request.url.path,
                client_ip=request.client.host if request.client else "unknown",
            )
            raise HTTPException(status_code=401, detail="Authentication failed")

        return await call_next(request)


def _safe_error_detail(original_error: Exception, public_message: str) -> str:
    """Log the full error server-side, return a safe message to the client."""
    logger.error(
        "internal_error",
        error_type=type(original_error).__name__,
        error_message=str(original_error),
        exc_info=True,
    )
    return public_message


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    region = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west3")

    app.state.registry = InMemoryToolRegistry()
    app.state.memory = FirestoreMemory(project_id=project_id or "local-dev")
    app.state.agent = ADKAgent(
        config=AgentConfig(
            name="agentic-workflow",
            model=os.getenv("AGENT_MODEL", "gemini-2.5-flash"),
            system_prompt=os.getenv("AGENT_SYSTEM_PROMPT"),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("AGENT_MAX_TOKENS", "8192")),
        ),
        registry=app.state.registry,
    )

    logger.info("Agentic Workflow server started", project=project_id, region=region)

    try:
        yield
    finally:
        logger.info("Agentic Workflow server shutting down")
        try:
            await app.state.agent.close()
        except Exception as e:
            logger.warning(f"Error closing agent: {e}")


app = FastAPI(
    title="Agentic Workflow API",
    description="Extensible AI agent platform with framework-agnostic architecture",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
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
async def health(
    reg: InMemoryToolRegistry = Depends(get_registry),
) -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        agent="agentic-workflow",
        tools=reg.list_tools(),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    mem: FirestoreMemory = Depends(get_memory),
    agt: ADKAgent = Depends(get_agent),
) -> ChatResponse:
    """
    Main chat endpoint.

    Accepts a user message and returns the agent's response.
    Maintains conversation context via session_id.
    """
    session_id = request.session_id
    user_id = request.user_id

    # Load existing session history
    history = await mem.get_session(session_id) or []

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
        name=agt.config.name,
        model=agt.config.model,
        system_prompt=agt.config.system_prompt,
        temperature=agt.config.temperature,
        max_tokens=agt.config.max_tokens,
        tools=request.tools or agt.config.tools,
        metadata={"session_id": session_id, "user_id": user_id},
    )

    # Invoke agent
    start_time = time.time()
    response = await agt.invoke(messages, config)
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
    await mem.save_session(session_id, messages)

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
async def chat_stream(
    request: ChatRequest,
    mem: FirestoreMemory = Depends(get_memory),
    agt: ADKAgent = Depends(get_agent),
) -> StreamingResponse:
    """Streaming chat endpoint for real-time responses."""
    session_id = request.session_id
    user_id = request.user_id
    history = await mem.get_session(session_id) or []

    messages = list(history)
    messages.append(
        Message(
            role=MessageRole.USER,
            content=request.message,
            metadata={"user_id": user_id},
        )
    )

    config = AgentConfig(
        name=agt.config.name,
        model=agt.config.model,
        system_prompt=agt.config.system_prompt,
        temperature=agt.config.temperature,
        max_tokens=agt.config.max_tokens,
        tools=request.tools or agt.config.tools,
        metadata={"session_id": session_id, "user_id": user_id},
    )

    async def generate() -> AsyncGenerator[str, None]:
        full_response = ""
        async for chunk in agt.stream(messages, config):
            full_response += chunk
            yield f"data: {chunk}\n\n"

        # Save session after streaming completes
        messages.append(
            Message(
                role=MessageRole.ASSISTANT,
                content=full_response,
            )
        )
        await mem.save_session(session_id, messages)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/tools/register")
async def register_tool(
    request: ToolRegistrationRequest,
    reg: InMemoryToolRegistry = Depends(get_registry),
) -> dict[str, Any]:
    """Register a new MCP tool dynamically."""
    try:
        tools = await reg.discover(request.source)
        registered = []
        for tool in tools:
            reg.register(tool)
            registered.append(tool.name)

        return {
            "status": "success",
            "registered": registered,
            "count": len(registered),
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=_safe_error_detail(e, "Invalid tool source or discovery failed"),
        )


@app.get("/tools", response_model=list[str])
async def list_tools(
    reg: InMemoryToolRegistry = Depends(get_registry),
) -> list[str]:
    """List all registered tools."""
    return reg.list_tools()


@app.post("/tools/{tool_name}/invoke")
async def invoke_tool(
    tool_name: str,
    arguments: dict[str, Any],
    reg: InMemoryToolRegistry = Depends(get_registry),
) -> dict[str, Any]:
    """Invoke a tool directly."""
    tool = reg.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    try:
        result = await tool.execute(arguments)
        return {"tool": tool_name, "result": result, "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_safe_error_detail(e, "Tool execution failed"),
        )


@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    mem: FirestoreMemory = Depends(get_memory),
) -> dict[str, str]:
    """Delete a conversation session."""
    await mem.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)), log_config=None)
