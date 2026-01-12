#!/usr/bin/env python3
"""
MCP Client with Structured Logging

Example integration showing:
- State transitions (connecting, connected, disconnected, error)
- Tool call tracking
- Reconnection handling
- Message queuing metrics
- Transport layer events

Usage:
    from scripts.core.mcp_client_logged import MCPClient, create_client

    client = create_client("mcp-server-name")
    await client.connect()
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable
from enum import Enum

from scripts.core.logging_config import (
    get_logger,
    setup_logging,
    generate_correlation_id,
    StructuredLogger,
)


# =============================================================================
# Logger Setup
# =============================================================================

logger = get_logger("mcp_client", "mcp_client")


# =============================================================================
# State Enums and Constants
# =============================================================================

class ClientState(Enum):
    """MCP client states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    CLOSED = "closed"


# =============================================================================
# Logging Wrappers
# =============================================================================

def log_state_transition(
    client_name: str,
    from_state: ClientState,
    to_state: ClientState,
    correlation_id: str,
    reason: str | None = None,
) -> None:
    """Log state transitions."""
    logger.info(
        f"State transition: {from_state.value} -> {to_state.value}",
        trace_id=correlation_id,
        operation="state_transition",
        client_name=client_name,
        from_state=from_state.value,
        to_state=to_state.value,
        reason=reason,
    )


def log_connection_attempt(
    client_name: str,
    server_url: str,
    correlation_id: str,
    attempt_number: int = 1,
) -> None:
    """Log connection attempt."""
    logger.info(
        "Connection attempt",
        trace_id=correlation_id,
        operation="connection_attempt",
        client_name=client_name,
        server_url=server_url,
        attempt_number=attempt_number,
    )


def log_connection_success(
    client_name: str,
    server_url: str,
    correlation_id: str,
    duration_ms: float,
) -> None:
    """Log successful connection."""
    logger.info(
        "Connected successfully",
        trace_id=correlation_id,
        operation="connection_success",
        client_name=client_name,
        server_url=server_url,
        duration_ms=round(duration_ms, 2),
    )


def log_connection_failure(
    client_name: str,
    server_url: str,
    correlation_id: str,
    error: str,
    will_retry: bool,
    attempt_number: int,
) -> None:
    """Log connection failure."""
    logger.warning(
        "Connection failed",
        trace_id=correlation_id,
        operation="connection_failure",
        client_name=client_name,
        server_url=server_url,
        error=error,
        will_retry=will_retry,
        attempt_number=attempt_number,
    )


def log_reconnection_scheduled(
    client_name: str,
    correlation_id: str,
    delay_seconds: int,
    attempt_number: int,
) -> None:
    """Log scheduled reconnection."""
    logger.info(
        "Reconnection scheduled",
        trace_id=correlation_id,
        operation="reconnection_scheduled",
        client_name=client_name,
        delay_seconds=delay_seconds,
        attempt_number=attempt_number,
    )


def log_reconnection_success(
    client_name: str,
    correlation_id: str,
    attempt_number: int,
    duration_ms: float,
) -> None:
    """Log successful reconnection."""
    logger.info(
        "Reconnected successfully",
        trace_id=correlation_id,
        operation="reconnection_success",
        client_name=client_name,
        attempt_number=attempt_number,
        duration_ms=round(duration_ms, 2),
    )


def log_tool_call(
    client_name: str,
    tool_name: str,
    correlation_id: str,
    call_id: str,
    arguments_size: int | None = None,
) -> None:
    """Log tool call initiation."""
    logger.debug(
        "Tool call initiated",
        trace_id=correlation_id,
        operation="tool_call",
        client_name=client_name,
        tool_name=tool_name,
        call_id=call_id,
        arguments_size=arguments_size,
    )


def log_tool_result(
    client_name: str,
    tool_name: str,
    correlation_id: str,
    call_id: str,
    success: bool,
    duration_ms: float,
    error: str | None = None,
) -> None:
    """Log tool call result."""
    if success:
        logger.debug(
            "Tool call completed",
            trace_id=correlation_id,
            operation="tool_result",
            client_name=client_name,
            tool_name=tool_name,
            call_id=call_id,
            duration_ms=round(duration_ms, 2),
        )
    else:
        logger.warning(
            "Tool call failed",
            trace_id=correlation_id,
            operation="tool_result",
            client_name=client_name,
            tool_name=tool_name,
            call_id=call_id,
            error=error,
            duration_ms=round(duration_ms, 2),
        )


def log_message_sent(
    client_name: str,
    message_type: str,
    correlation_id: str,
    size_bytes: int,
) -> None:
    """Log message sent."""
    logger.debug(
        "Message sent",
        trace_id=correlation_id,
        operation="message_sent",
        client_name=client_name,
        message_type=message_type,
        size_bytes=size_bytes,
    )


def log_message_received(
    client_name: str,
    message_type: str,
    correlation_id: str,
    size_bytes: int,
) -> None:
    """Log message received."""
    logger.debug(
        "Message received",
        trace_id=correlation_id,
        operation="message_received",
        client_name=client_name,
        message_type=message_type,
        size_bytes=size_bytes,
    )


def log_queue_metrics(
    client_name: str,
    correlation_id: str,
    queue_size: int,
    max_queue_size: int,
    dropped_count: int = 0,
) -> None:
    """Log message queue metrics."""
    logger.debug(
        "Queue metrics",
        trace_id=correlation_id,
        operation="queue_metrics",
        client_name=client_name,
        queue_size=queue_size,
        max_queue_size=max_queue_size,
        dropped_count=dropped_count,
    )


def log_error(
    client_name: str,
    error_type: str,
    error_message: str,
    correlation_id: str,
    operation: str = "unknown",
    will_reconnect: bool = False,
) -> None:
    """Log error with context."""
    logger.error(
        f"Error during {operation}",
        trace_id=correlation_id,
        operation=operation,
        client_name=client_name,
        error_type=error_type,
        error_message=error_message,
        will_reconnect=will_reconnect,
    )


def log_disconnect(
    client_name: str,
    correlation_id: str,
    reason: str | None = None,
    was_clean: bool = False,
) -> None:
    """Log disconnection."""
    logger.info(
        "Disconnected",
        trace_id=correlation_id,
        operation="disconnect",
        client_name=client_name,
        reason=reason,
        was_clean=was_clean,
    )


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ClientConfig:
    """MCP client configuration."""
    server_url: str
    name: str = "mcp-client"
    max_reconnect_attempts: int = 5
    reconnect_delay_seconds: int = 1
    max_queue_size: int = 100
    message_timeout_seconds: float = 30.0


@dataclass
class Message:
    """MCP message."""
    message_type: str
    payload: dict[str, Any]
    correlation_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class ToolCall:
    """Tool call tracking."""
    tool_name: str
    call_id: str
    arguments: dict[str, Any] | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    success: bool = False
    error: str | None = None


# =============================================================================
# MCP Client with Logging
# =============================================================================

class MCPClient:
    """MCP client with comprehensive logging."""

    def __init__(
        self,
        config: ClientConfig,
        on_state_change: Callable[[ClientState], None] | None = None,
        on_message: Callable[[Message], None] | None = None,
        on_tool_result: Callable[[ToolCall], None] | None = None,
    ):
        self.config = config
        self.on_state_change = on_state_change
        self.on_message = on_message
        self.on_tool_result = on_tool_result

        self._state = ClientState.DISCONNECTED
        self._correlation_id = generate_correlation_id()
        self._connection_attempt = 0
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=config.max_queue_size)
        self._active_calls: dict[str, ToolCall] = {}

        self._reconnect_task: asyncio.Task | None = None
        self._processing_task: asyncio.Task | None = None

    @property
    def state(self) -> ClientState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == ClientState.CONNECTED

    @property
    def correlation_id(self) -> str:
        return self._correlation_id

    def _set_state(self, new_state: ClientState, reason: str | None = None) -> None:
        """Set state and log transition."""
        old_state = self._state
        if old_state != new_state:
            log_state_transition(
                self.config.name,
                old_state,
                new_state,
                self._correlation_id,
                reason=reason,
            )
            self._state = new_state
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    logger.warning(
                        "State change callback error",
                        trace_id=self._correlation_id,
                        error=str(e),
                    )

    async def connect(self) -> bool:
        """Connect to MCP server with logging."""
        self._correlation_id = generate_correlation_id()
        self._connection_attempt = 0

        log_connection_attempt(
            self.config.name,
            self.config.server_url,
            self._correlation_id,
            attempt_number=1,
        )

        return await self._do_connect()

    async def _do_connect(self) -> bool:
        """Internal connection logic."""
        self._set_state(ClientState.CONNECTING)
        self._connection_attempt += 1

        start_time = datetime.now(timezone.utc).timestamp()

        try:
            # Simulate connection (replace with actual MCP connection)
            await asyncio.sleep(0.1)  # Simulate network latency

            duration_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
            log_connection_success(
                self.config.name,
                self.config.server_url,
                self._correlation_id,
                duration_ms,
            )

            self._set_state(ClientState.CONNECTED, reason="connection successful")

            # Start message processing
            self._processing_task = asyncio.create_task(self._process_messages())

            return True

        except Exception as e:
            error_str = str(e)
            will_retry = self._connection_attempt < self.config.max_reconnect_attempts

            log_connection_failure(
                self.config.name,
                self.config.server_url,
                self._correlation_id,
                error=error_str,
                will_retry=will_retry,
                attempt_number=self._connection_attempt,
            )

            if will_retry:
                return await self._schedule_reconnect()
            else:
                self._set_state(ClientState.ERROR, reason="max retries exceeded")
                log_error(
                    self.config.name,
                    type(e).__name__,
                    error_str,
                    self._correlation_id,
                    operation="connect",
                    will_reconnect=False,
                )
                return False

    async def _schedule_reconnect(self) -> bool:
        """Schedule a reconnection attempt."""
        self._set_state(ClientState.RECONNECTING)
        self._connection_attempt += 1

        delay = min(
            self.config.reconnect_delay_seconds * (2 ** (self._connection_attempt - 1)),
            60,  # Cap at 60 seconds
        )

        log_reconnection_scheduled(
            self.config.name,
            self._correlation_id,
            delay_seconds=delay,
            attempt_number=self._connection_attempt,
        )

        await asyncio.sleep(delay)

        log_connection_attempt(
            self.config.name,
            self.config.server_url,
            self._correlation_id,
            attempt_number=self._connection_attempt,
        )

        return await self._do_connect()

    async def disconnect(self, clean: bool = True) -> None:
        """Disconnect from server."""
        log_disconnect(
            self.config.name,
            self._correlation_id,
            reason="client disconnect",
            was_clean=clean,
        )

        # Cancel tasks
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        if self._reconnect_task:
            self._reconnect_task.cancel()

        self._set_state(ClientState.CLOSED if clean else ClientState.DISCONNECTED)

    async def send_message(self, message: Message) -> bool:
        """Send a message with logging."""
        if not self.is_connected:
            logger.warning(
                "Cannot send message - not connected",
                trace_id=self._correlation_id,
                operation="send_message",
                client_name=self.config.name,
            )
            return False

        try:
            self._message_queue.put_nowait(message)

            log_message_sent(
                self.config.name,
                message.message_type,
                self._correlation_id,
                size_bytes=len(json.dumps(message.payload)),
            )

            log_queue_metrics(
                self.config.name,
                self._correlation_id,
                queue_size=self._message_queue.qsize(),
                max_queue_size=self.config.max_queue_size,
            )

            return True

        except asyncio.QueueFull:
            logger.warning(
                "Message queue full",
                trace_id=self._correlation_id,
                operation="send_message",
                client_name=self.config.name,
                max_queue_size=self.config.max_queue_size,
            )
            return False

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a tool with logging."""
        if not self.is_connected:
            raise RuntimeError("Not connected to server")

        call_id = generate_correlation_id()
        tool_call = ToolCall(
            tool_name=tool_name,
            call_id=call_id,
            arguments=arguments,
        )
        self._active_calls[call_id] = tool_call

        log_tool_call(
            self.config.name,
            tool_name,
            self._correlation_id,
            call_id,
            arguments_size=len(json.dumps(arguments)) if arguments else 0,
        )

        start_time = datetime.now(timezone.utc).timestamp()

        try:
            # Simulate tool call (replace with actual MCP call)
            await asyncio.sleep(0.05)

            duration_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000

            tool_call.success = True
            tool_call.completed_at = datetime.now(UTC).isoformat()

            log_tool_result(
                self.config.name,
                tool_name,
                self._correlation_id,
                call_id,
                success=True,
                duration_ms=duration_ms,
            )

            if self.on_tool_result:
                self.on_tool_result(tool_call)

            return {"success": True, "call_id": call_id}

        except Exception as e:
            duration_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
            error_str = str(e)

            tool_call.success = False
            tool_call.error = error_str
            tool_call.completed_at = datetime.now(UTC).isoformat()

            log_tool_result(
                self.config.name,
                tool_name,
                self._correlation_id,
                call_id,
                success=False,
                duration_ms=duration_ms,
                error=error_str,
            )

            if self.on_tool_result:
                self.on_tool_result(tool_call)

            raise

    async def _process_messages(self) -> None:
        """Process messages from queue."""
        while self.is_connected:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0,
                )

                log_message_received(
                    self.config.name,
                    message.message_type,
                    self._correlation_id,
                    size_bytes=len(json.dumps(message.payload)),
                )

                # Process message (replace with actual processing)
                await asyncio.sleep(0.01)

                if self.on_message:
                    try:
                        self.on_message(message)
                    except Exception as e:
                        logger.warning(
                            "Message callback error",
                            trace_id=self._correlation_id,
                            error=str(e),
                        )

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error(
                    self.config.name,
                    type(e).__name__,
                    str(e),
                    self._correlation_id,
                    operation="message_processing",
                    will_reconnect=False,
                )

    def get_state(self) -> dict:
        """Get client state for monitoring."""
        return {
            "name": self.config.name,
            "state": self._state.value,
            "correlation_id": self._correlation_id,
            "connection_attempt": self._connection_attempt,
            "queue_size": self._message_queue.qsize(),
            "max_queue_size": self.config.max_queue_size,
            "active_calls": len(self._active_calls),
            "is_connected": self.is_connected,
        }


# =============================================================================
# Factory Function
# =============================================================================

def create_client(
    server_url: str,
    name: str = "mcp-client",
    max_reconnect_attempts: int = 5,
    reconnect_delay_seconds: int = 1,
    max_queue_size: int = 100,
    on_state_change: Callable[[ClientState], None] | None = None,
    on_message: Callable[[Message], None] | None = None,
    on_tool_result: Callable[[ToolCall], None] | None = None,
) -> MCPClient:
    """Create a new MCP client with logging.

    Args:
        server_url: MCP server URL
        name: Client name for logging
        max_reconnect_attempts: Maximum reconnection attempts
        reconnect_delay_seconds: Initial reconnect delay (exponential backoff)
        max_queue_size: Maximum outgoing message queue size
        on_state_change: Callback when state changes
        on_message: Callback for received messages
        on_tool_result: Callback for tool call results

    Returns:
        Configured MCPClient instance
    """
    config = ClientConfig(
        server_url=server_url,
        name=name,
        max_reconnect_attempts=max_reconnect_attempts,
        reconnect_delay_seconds=reconnect_delay_seconds,
        max_queue_size=max_queue_size,
    )

    return MCPClient(
        config=config,
        on_state_change=on_state_change,
        on_message=on_message,
        on_tool_result=on_tool_result,
    )
