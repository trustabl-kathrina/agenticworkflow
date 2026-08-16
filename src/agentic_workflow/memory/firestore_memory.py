"""
Memory abstraction layer for agent sessions and long-term memory.

Provides Firestore-backed implementation for GCP, with the IMemory interface
allowing swap to Redis, Vertex AI Memory Bank, or other backends.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import UTC
from typing import Any, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agentic_workflow.core.interfaces import IMemory, Message

try:
    from google.api_core.exceptions import DeadlineExceeded, ServiceUnavailable
    from google.cloud.firestore import SERVER_TIMESTAMP, AsyncClient
except ImportError:
    SERVER_TIMESTAMP = None  # type: ignore[assignment]
    AsyncClient = None  # type: ignore[assignment,misc]
    ServiceUnavailable = Exception  # type: ignore[misc,assignment]
    DeadlineExceeded = Exception  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _firestore_retry_decorator(func: F) -> F:  # noqa: UP047
    """Retry decorator for Firestore operations with exponential backoff."""
    return retry(
        retry=retry_if_exception_type((ServiceUnavailable, DeadlineExceeded)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )(func)


class FirestoreMemory(IMemory):
    """
    Firestore-backed memory implementation for GCP.

    Stores conversation sessions as documents in Firestore with TTL support.
    """

    def __init__(
        self,
        project_id: str,
        database_id: str = "(default)",
        location: str = "europe-west3",
        session_ttl: int | None = None,
    ) -> None:
        self.project_id = project_id
        self.database_id = database_id
        self.location = location
        self.session_ttl = session_ttl  # seconds
        self._client: Any = None

    async def _get_client(self) -> Any:
        """Lazy Firestore client initialization."""
        if self._client is None:
            if AsyncClient is None:
                raise ImportError(
                    "google-cloud-firestore is required for FirestoreMemory. "
                    "Install it with: pip install google-cloud-firestore"
                )
            self._client = AsyncClient(
                project=self.project_id,
                database=self.database_id,
            )
        return self._client

    def _session_doc(self, session_id: str) -> str:
        return f"sessions/{session_id}"

    @_firestore_retry_decorator
    async def get_session(self, session_id: str) -> list[Message] | None:
        """Retrieve messages for a session."""
        client = await self._get_client()
        doc_ref = client.document(self._session_doc(session_id))
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        messages_data = data.get("messages", [])
        return [Message(**m) for m in messages_data]

    @_firestore_retry_decorator
    async def save_session(
        self,
        session_id: str,
        messages: Sequence[Message],
        ttl: int | None = None,
    ) -> None:
        """Persist messages for a session."""
        client = await self._get_client()
        doc_ref = client.document(self._session_doc(session_id))

        messages_data = [
            {
                "role": m.role.value,
                "content": m.content,
                "metadata": m.metadata,
                "tool_calls": [tc.__dict__ for tc in m.tool_calls],
                "tool_call_id": m.tool_call_id,
            }
            for m in messages
        ]

        doc_data: dict[str, Any] = {
            "messages": messages_data,
            "message_count": len(messages_data),
            "updated_at": SERVER_TIMESTAMP,
        }

        effective_ttl = ttl or self.session_ttl
        if effective_ttl:
            from datetime import datetime, timedelta

            doc_data["expires_at"] = datetime.now(UTC) + timedelta(
                seconds=effective_ttl
            )

        await doc_ref.set(doc_data, merge=True)
        logger.debug(f"Saved session {session_id} with {len(messages_data)} messages")

    @_firestore_retry_decorator
    async def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        client = await self._get_client()
        doc_ref = client.document(self._session_doc(session_id))
        await doc_ref.delete()

    @_firestore_retry_decorator
    async def search(
        self, query: str, limit: int = 10, session_id: str | None = None
    ) -> list[Message]:
        """Search across sessions for relevant messages."""
        client = await self._get_client()
        collection = client.collection("sessions")

        if session_id:
            doc = await collection.document(session_id).get()
            if not doc.exists:
                return []
            data = doc.to_dict()
            messages_data = data.get("messages", [])
            all_messages = [Message(**m) for m in messages_data]
        else:
            all_messages = []
            async for doc in collection.stream():
                data = doc.to_dict()
                messages_data = data.get("messages", [])
                all_messages.extend(Message(**m) for m in messages_data)

        query_lower = query.lower()
        scored = []
        for msg in all_messages:
            if query_lower in msg.content.lower():
                scored.append((msg, msg.content.lower().count(query_lower)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [msg for msg, _ in scored[:limit]]
