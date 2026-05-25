"""WebSocket Manager - Real-time agent activity streaming."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    """Manage WebSocket connections for real-time agent updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.message_queue: list[dict[str, Any]] = []
        self.max_queue_size = 1000

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection.
        
        Args:
            websocket: FastAPI WebSocket connection
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Disconnect a WebSocket connection.
        
        Args:
            websocket: FastAPI WebSocket connection
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast_agent_message(
        self, agent: str, action: str, data: dict[str, Any]
    ) -> None:
        """Broadcast agent activity to all connected clients.
        
        Args:
            agent: Agent name
            action: Action performed
            data: Action data
        """

        message = {
            "type": "agent_message",
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "action": action,
            "data": data,
        }

        self._queue_message(message)

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS] Error sending message: {e}")
                self.disconnect(connection)

    async def broadcast_llm_interaction(
        self,
        agent: str,
        direction: str,
        prompt: str,
        response: str | dict[str, Any] | None = None,
    ) -> None:
        """Broadcast LLM interactions for observability.
        
        Args:
            agent: Agent name
            direction: "request" or "response"
            prompt: Prompt sent to LLM
            response: Response from LLM
        """

        message = {
            "type": "llm_interaction",
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "direction": direction,
            "prompt": prompt[:500] if isinstance(prompt, str) else str(prompt)[:500],
            "response": (
                response[:500] if isinstance(response, str) else json.dumps(response)[:500]
            ),
            "full_prompt": prompt,
            "full_response": response,
        }

        self._queue_message(message)

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS] Error sending LLM message: {e}")
                self.disconnect(connection)

    async def broadcast_execution_log(
        self,
        stage_id: str,
        stage_name: str,
        message: str,
        level: str = "info",
    ) -> None:
        """Broadcast execution log messages.
        
        Args:
            stage_id: Stage ID
            stage_name: Stage name
            message: Log message
            level: Log level (info, warning, error, success)
        """

        log_message = {
            "type": "execution_log",
            "timestamp": datetime.now().isoformat(),
            "stage_id": stage_id,
            "stage_name": stage_name,
            "message": message,
            "level": level,
        }

        self._queue_message(log_message)

        for connection in self.active_connections:
            try:
                await connection.send_json(log_message)
            except Exception as e:
                print(f"[WS] Error sending log: {e}")
                self.disconnect(connection)

    async def broadcast_credentials_generated(
        self, server_ip: str, services: list[str]
    ) -> None:
        """Broadcast credentials generation event.
        
        Args:
            server_ip: Server IP
            services: List of services with generated credentials
        """

        message = {
            "type": "credentials_generated",
            "timestamp": datetime.now().isoformat(),
            "server_ip": server_ip,
            "services": services,
            "count": len(services),
        }

        self._queue_message(message)

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS] Error sending credentials message: {e}")
                self.disconnect(connection)

    async def broadcast_error(
        self, error_type: str, message: str, context: dict[str, Any] | None = None
    ) -> None:
        """Broadcast error messages.
        
        Args:
            error_type: Type of error
            message: Error message
            context: Optional error context
        """

        error_message = {
            "type": "error",
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "message": message,
            "context": context or {},
        }

        self._queue_message(error_message)

        for connection in self.active_connections:
            try:
                await connection.send_json(error_message)
            except Exception as e:
                print(f"[WS] Error sending error message: {e}")
                self.disconnect(connection)

    async def broadcast_status(self, status: str, details: dict[str, Any]) -> None:
        """Broadcast pipeline status updates.
        
        Args:
            status: Status (started, running, completed, failed)
            details: Status details
        """

        status_message = {
            "type": "status",
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "details": details,
        }

        self._queue_message(status_message)

        for connection in self.active_connections:
            try:
                await connection.send_json(status_message)
            except Exception as e:
                print(f"[WS] Error sending status: {e}")
                self.disconnect(connection)

    def _queue_message(self, message: dict[str, Any]) -> None:
        """Queue message for historical retrieval.
        
        Args:
            message: Message to queue
        """
        self.message_queue.append(message)
        if len(self.message_queue) > self.max_queue_size:
            self.message_queue.pop(0)

    def get_message_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get message history.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of recent messages.
        """
        return self.message_queue[-limit:] if limit > 0 else self.message_queue

    def get_agent_messages(self, agent: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get messages for specific agent.
        
        Args:
            agent: Agent name
            limit: Maximum messages
            
        Returns:
            List of agent messages.
        """
        return [msg for msg in self.message_queue[-limit:] if msg.get("agent") == agent]

    def get_llm_interactions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get all LLM interactions.
        
        Args:
            limit: Maximum interactions
            
        Returns:
            List of LLM interactions.
        """
        return [
            msg
            for msg in self.message_queue[-limit:]
            if msg.get("type") == "llm_interaction"
        ]

    def clear_history(self) -> None:
        """Clear message history."""
        self.message_queue.clear()
        print("[WS] Message history cleared")
