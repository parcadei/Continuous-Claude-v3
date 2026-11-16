"""
WebSocket Multiplexer for Agentica Agent Sessions

Provides session registration, agent lifecycle management, and WebSocket
multiplexing for streaming responses from multiple concurrent agents.

Architecture:
    SessionRegistry -> tracks client sessions by X-Client-Session-ID
    AgentRegistry   -> tracks agents by UID, maps to sessions
    WebSocketHub    -> handles /socket connections and message routing

Protocol:
    Incoming (client -> server):
        {"agent_uid": "xxx", "type": "prompt", "payload": {...}}
        {"agent_uid": "xxx", "type": "cancel"}

    Outgoing (server -> client):
        {"agent_uid": "xxx", "type": "chunk", "content": "..."}
        {"agent_uid": "xxx", "type": "done"}
        {"agent_uid": "xxx", "type": "error", "message": "..."}

Usage:
    from websocket_multiplex import (
        SessionRegistry,
        AgentRegistry,
        WebSocketHub,
        register_websocket_routes,
    )

    # Create registries (singleton or per-app)
    sessions = SessionRegistry()
    agents = AgentRegistry(sessions)
    hub = WebSocketHub(agents)

    # Register routes on FastAPI app
    register_websocket_routes(app, sessions, agents, hub)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


# ============================================================================
# Constants
# ============================================================================

DEFAULT_AGENT_TIMEOUT = 900  # 15 minutes


# ============================================================================
# Message Types
# ============================================================================


class MessageType(str, Enum):
    """WebSocket message types."""
    PROMPT = "prompt"      # Client sends a prompt to agent
    CANCEL = "cancel"      # Client cancels agent execution
    CHUNK = "chunk"        # Server sends response chunk
    DONE = "done"          # Server signals completion
    ERROR = "error"        # Server signals error


# ============================================================================
# Request/Response Models
# ============================================================================


class AgentCreateRequest(BaseModel):
    """Request body for creating an agent."""
    system: str | None = None       # System prompt
    model: str = "claude-sonnet"    # Model to use
    max_tokens: int | None = None   # Max response tokens
    temperature: float | None = None


class WebSocketMessage(BaseModel):
    """Message format for WebSocket communication."""
    agent_uid: str
    type: MessageType
    payload: dict[str, Any] | None = None
    content: str | None = None
    message: str | None = None


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ClientSession:
    """Represents a registered client session."""
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    agent_uids: set[str] = field(default_factory=set)
    websocket: WebSocket | None = None
    last_activity: datetime = field(default_factory=datetime.now)


@dataclass
class Agent:
    """Represents a created agent."""
    uid: str
    session_id: str
    system: str | None
    model: str
    max_tokens: int | None
    temperature: float | None
    created_at: datetime = field(default_factory=datetime.now)
    task: asyncio.Task | None = None  # Running task if any
    cancelled: bool = False


# ============================================================================
# Session Registry
# ============================================================================


class SessionRegistry:
    """Registry for client sessions.

    Tracks sessions by X-Client-Session-ID header.
    Thread-safe via asyncio locks.
    """

    def __init__(self):
        self._sessions: dict[str, ClientSession] = {}
        self._lock = asyncio.Lock()

    async def register(self, session_id: str) -> ClientSession:
        """Register a new client session.

        Args:
            session_id: Client-provided session ID (from header)

        Returns:
            Created or existing ClientSession
        """
        async with self._lock:
            if session_id in self._sessions:
                # Update last activity
                self._sessions[session_id].last_activity = datetime.now()
                return self._sessions[session_id]

            session = ClientSession(session_id=session_id)
            self._sessions[session_id] = session
            return session

    async def get(self, session_id: str) -> ClientSession | None:
        """Get session by ID."""
        async with self._lock:
            return self._sessions.get(session_id)

    async def update_websocket(
        self,
        session_id: str,
        websocket: WebSocket | None
    ) -> None:
        """Associate/disassociate WebSocket with session."""
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].websocket = websocket
                self._sessions[session_id].last_activity = datetime.now()

    async def add_agent(self, session_id: str, agent_uid: str) -> None:
        """Add agent UID to session's agent set."""
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].agent_uids.add(agent_uid)
                self._sessions[session_id].last_activity = datetime.now()

    async def remove_agent(self, session_id: str, agent_uid: str) -> None:
        """Remove agent UID from session's agent set."""
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].agent_uids.discard(agent_uid)

    async def cleanup_stale(self, max_age_seconds: int = 3600) -> int:
        """Remove sessions older than max_age_seconds.

        Returns:
            Number of sessions removed
        """
        async with self._lock:
            now = datetime.now()
            stale = [
                sid for sid, session in self._sessions.items()
                if (now - session.last_activity).total_seconds() > max_age_seconds
            ]
            for sid in stale:
                del self._sessions[sid]
            return len(stale)

    @property
    def count(self) -> int:
        """Number of registered sessions."""
        return len(self._sessions)


# ============================================================================
# Agent Registry
# ============================================================================


class AgentRegistry:
    """Registry for agents.

    Tracks agents by UID, maps to sessions.
    Thread-safe via asyncio locks.
    Optionally persists to CoordinationDB for observability.
    """

    def __init__(
        self,
        sessions: SessionRegistry,
        coordination_db: "CoordinationDB | None" = None,
    ):
        self._sessions = sessions
        self._agents: dict[str, Agent] = {}
        self._lock = asyncio.Lock()
        self._coordination_db = coordination_db

    async def create(
        self,
        session_id: str,
        system: str | None = None,
        model: str = "claude-sonnet",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Agent:
        """Create a new agent.

        Args:
            session_id: Session to associate with
            system: System prompt
            model: Model name
            max_tokens: Max response tokens
            temperature: Sampling temperature

        Returns:
            Created Agent

        Raises:
            ValueError: If session not found
        """
        # Verify session exists
        session = await self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        uid = uuid.uuid4().hex[:12]

        async with self._lock:
            agent = Agent(
                uid=uid,
                session_id=session_id,
                system=system,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            self._agents[uid] = agent

        # Update session's agent list
        await self._sessions.add_agent(session_id, uid)

        # Persist to CoordinationDB for observability
        if self._coordination_db:
            self._coordination_db.register_agent(
                agent_id=uid,
                premise=system,
                model=model,
                source="websocket",
            )

        return agent

    async def get(self, uid: str) -> Agent | None:
        """Get agent by UID."""
        async with self._lock:
            return self._agents.get(uid)

    async def destroy(self, uid: str, status: str = "completed", error: str | None = None) -> bool:
        """Destroy an agent.

        Cancels any running task and removes from registry.

        Args:
            uid: Agent UID
            status: Completion status ("completed" or "failed")
            error: Optional error message if failed

        Returns:
            True if agent was found and destroyed
        """
        async with self._lock:
            agent = self._agents.pop(uid, None)
            if agent is None:
                return False

            # Cancel running task if any
            if agent.task and not agent.task.done():
                agent.cancelled = True
                agent.task.cancel()

        # Remove from session
        await self._sessions.remove_agent(agent.session_id, uid)

        # Mark completed in CoordinationDB
        if self._coordination_db:
            self._coordination_db.complete_agent(
                agent_id=uid,
                status=status,
                error_message=error,
            )

        return True

    async def set_task(self, uid: str, task: asyncio.Task) -> None:
        """Associate a running task with an agent."""
        async with self._lock:
            if uid in self._agents:
                self._agents[uid].task = task

    async def cancel(self, uid: str) -> bool:
        """Cancel agent's running task.

        Returns:
            True if task was cancelled
        """
        async with self._lock:
            agent = self._agents.get(uid)
            if agent is None:
                return False

            if agent.task and not agent.task.done():
                agent.cancelled = True
                agent.task.cancel()
                return True

            return False

    @property
    def count(self) -> int:
        """Number of registered agents."""
        return len(self._agents)


# ============================================================================
# WebSocket Hub
# ============================================================================


class WebSocketHub:
    """WebSocket multiplexer for agent communication.

    Handles:
    - WebSocket connections per session
    - Message routing to/from agents
    - Concurrent agent execution
    """

    def __init__(
        self,
        agents: AgentRegistry,
        executor: Callable[[Agent, str], AsyncGenerator[str, None]] | None = None,
    ):
        """Initialize WebSocket hub.

        Args:
            agents: Agent registry
            executor: Async generator function that takes (Agent, prompt) and
                     yields response chunks. If None, uses a mock executor.
        """
        self._agents = agents
        self._executor = executor or self._mock_executor
        self._connections: dict[str, WebSocket] = {}  # session_id -> websocket
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Handle new WebSocket connection.

        Args:
            session_id: Session ID from header
            websocket: WebSocket connection
        """
        await websocket.accept()

        async with self._lock:
            # Close existing connection for this session if any
            if session_id in self._connections:
                try:
                    await self._connections[session_id].close()
                except Exception:
                    pass

            self._connections[session_id] = websocket

    async def disconnect(self, session_id: str) -> None:
        """Handle WebSocket disconnection."""
        async with self._lock:
            self._connections.pop(session_id, None)

    async def handle_message(
        self,
        session_id: str,
        websocket: WebSocket,
        message: WebSocketMessage,
    ) -> None:
        """Handle incoming WebSocket message.

        Routes message to appropriate agent handler.

        Args:
            session_id: Client session ID
            websocket: WebSocket connection
            message: Parsed message
        """
        agent = await self._agents.get(message.agent_uid)

        if agent is None:
            await self._send_error(
                websocket,
                message.agent_uid,
                f"Agent {message.agent_uid} not found"
            )
            return

        if agent.session_id != session_id:
            await self._send_error(
                websocket,
                message.agent_uid,
                "Agent does not belong to this session"
            )
            return

        if message.type == MessageType.PROMPT:
            await self._handle_prompt(websocket, agent, message)
        elif message.type == MessageType.CANCEL:
            await self._handle_cancel(websocket, agent)

    async def _handle_prompt(
        self,
        websocket: WebSocket,
        agent: Agent,
        message: WebSocketMessage,
    ) -> None:
        """Handle prompt message - execute agent and stream response."""
        prompt = message.payload.get("prompt", "") if message.payload else ""

        if not prompt:
            await self._send_error(websocket, agent.uid, "Empty prompt")
            return

        # Create task for agent execution
        async def execute_and_stream():
            try:
                async for chunk in self._executor(agent, prompt):
                    if agent.cancelled:
                        break
                    await self._send_chunk(websocket, agent.uid, chunk)

                if not agent.cancelled:
                    await self._send_done(websocket, agent.uid)

            except asyncio.CancelledError:
                await self._send_error(websocket, agent.uid, "Cancelled")
            except Exception as e:
                await self._send_error(websocket, agent.uid, str(e))

        task = asyncio.create_task(execute_and_stream())
        await self._agents.set_task(agent.uid, task)

    async def _handle_cancel(
        self,
        websocket: WebSocket,
        agent: Agent,
    ) -> None:
        """Handle cancel message."""
        cancelled = await self._agents.cancel(agent.uid)
        if cancelled:
            await self._send_error(websocket, agent.uid, "Cancelled by client")

    async def _send_chunk(
        self,
        websocket: WebSocket,
        agent_uid: str,
        content: str,
    ) -> None:
        """Send chunk message."""
        msg = {
            "agent_uid": agent_uid,
            "type": MessageType.CHUNK.value,
            "content": content,
        }
        await websocket.send_json(msg)

    async def _send_done(
        self,
        websocket: WebSocket,
        agent_uid: str,
    ) -> None:
        """Send done message."""
        msg = {
            "agent_uid": agent_uid,
            "type": MessageType.DONE.value,
        }
        await websocket.send_json(msg)

    async def _send_error(
        self,
        websocket: WebSocket,
        agent_uid: str,
        message: str,
    ) -> None:
        """Send error message."""
        msg = {
            "agent_uid": agent_uid,
            "type": MessageType.ERROR.value,
            "message": message,
        }
        try:
            await websocket.send_json(msg)
        except Exception:
            pass  # Connection may be closed

    async def _mock_executor(
        self,
        agent: Agent,
        prompt: str,
    ) -> AsyncGenerator[str, None]:
        """Mock executor for testing."""
        # Simulate streaming response
        response = f"Mock response to: {prompt}"
        for word in response.split():
            yield word + " "
            await asyncio.sleep(0.1)


# ============================================================================
# Route Registration
# ============================================================================


def register_websocket_routes(
    app: FastAPI,
    sessions: SessionRegistry,
    agents: AgentRegistry,
    hub: WebSocketHub,
) -> None:
    """Register Agentica-compatible routes on FastAPI app.

    Registers:
        POST /session/register - Register client session
        POST /agent/create - Create agent
        DELETE /agent/destroy/{uid} - Destroy agent
        GET /socket - WebSocket endpoint

    Args:
        app: FastAPI application
        sessions: Session registry
        agents: Agent registry
        hub: WebSocket hub
    """

    @app.post("/session/register", response_class=Response)
    async def register_session(
        x_client_session_id: str = Header(..., alias="X-Client-Session-ID"),
    ) -> Response:
        """Register a client session.

        Requires X-Client-Session-ID header.
        Returns 200 OK with empty body.
        """
        await sessions.register(x_client_session_id)
        return Response(status_code=200)

    @app.post("/agent/create", response_class=PlainTextResponse)
    async def create_agent(
        request: AgentCreateRequest,
        x_client_session_id: str = Header(..., alias="X-Client-Session-ID"),
    ) -> PlainTextResponse:
        """Create a new agent.

        Requires X-Client-Session-ID header.
        Returns plain text agent UID.
        """
        session = await sessions.get(x_client_session_id)
        if session is None:
            raise HTTPException(
                status_code=400,
                detail="Session not registered. Call /session/register first."
            )

        agent = await agents.create(
            session_id=x_client_session_id,
            system=request.system,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

        return PlainTextResponse(agent.uid)

    @app.delete("/agent/destroy/{uid}")
    async def destroy_agent(
        uid: str,
        x_client_session_id: str = Header(..., alias="X-Client-Session-ID"),
    ) -> Response:
        """Destroy an agent.

        Requires X-Client-Session-ID header for authorization.
        Returns 200 OK on success, 404 if not found.
        """
        agent = await agents.get(uid)

        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")

        if agent.session_id != x_client_session_id:
            raise HTTPException(
                status_code=403,
                detail="Agent does not belong to this session"
            )

        await agents.destroy(uid)
        return Response(status_code=200)

    @app.websocket("/socket")
    async def websocket_endpoint(
        websocket: WebSocket,
    ):
        """WebSocket endpoint for agent communication.

        Expects X-Client-Session-ID in query params or headers.

        Protocol:
            Client -> Server:
                {"agent_uid": "xxx", "type": "prompt", "payload": {"prompt": "..."}}
                {"agent_uid": "xxx", "type": "cancel"}

            Server -> Client:
                {"agent_uid": "xxx", "type": "chunk", "content": "..."}
                {"agent_uid": "xxx", "type": "done"}
                {"agent_uid": "xxx", "type": "error", "message": "..."}
        """
        # Get session ID from query params or headers
        session_id = websocket.query_params.get("session_id")
        if not session_id:
            # Try headers (may not work for all WebSocket clients)
            session_id = websocket.headers.get("x-client-session-id")

        if not session_id:
            await websocket.close(code=4001, reason="Missing session_id")
            return

        # Verify session exists
        session = await sessions.get(session_id)
        if session is None:
            await websocket.close(code=4002, reason="Session not registered")
            return

        # Connect
        await hub.connect(session_id, websocket)
        await sessions.update_websocket(session_id, websocket)

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()

                try:
                    message = WebSocketMessage(**data)
                    await hub.handle_message(session_id, websocket, message)
                except Exception as e:
                    # Send error for malformed messages
                    agent_uid = data.get("agent_uid", "unknown")
                    await websocket.send_json({
                        "agent_uid": agent_uid,
                        "type": MessageType.ERROR.value,
                        "message": f"Invalid message: {e}",
                    })

        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            await hub.disconnect(session_id)
            await sessions.update_websocket(session_id, None)


# ============================================================================
# Factory Functions
# ============================================================================


def create_agentica_components(
    coordination_db: "CoordinationDB | None" = None,
) -> tuple[SessionRegistry, AgentRegistry, WebSocketHub]:
    """Create Agentica components with default configuration.

    Args:
        coordination_db: Optional CoordinationDB for agent tracking persistence

    Returns:
        Tuple of (SessionRegistry, AgentRegistry, WebSocketHub)
    """
    sessions = SessionRegistry()
    agents = AgentRegistry(sessions, coordination_db=coordination_db)
    hub = WebSocketHub(agents)
    return sessions, agents, hub


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "SessionRegistry",
    "AgentRegistry",
    "WebSocketHub",
    "Agent",
    "ClientSession",
    "AgentCreateRequest",
    "WebSocketMessage",
    "MessageType",
    "register_websocket_routes",
    "create_agentica_components",
]
