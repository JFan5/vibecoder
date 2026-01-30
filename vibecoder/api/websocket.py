"""WebSocket handler for real-time updates."""

import asyncio
import json
from datetime import datetime
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

from ..core.engine import get_engine
from ..storage.database import get_db


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        message_json = json.dumps(message, default=str)
        disconnected = set()

        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.add(connection)

        # Remove disconnected clients
        self.active_connections -= disconnected


# Global connection manager
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)

    # Start background task to send updates
    update_task = asyncio.create_task(send_updates(websocket))

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message.get("type") == "subscribe":
                # Client subscribing to specific task updates
                pass
            elif message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        update_task.cancel()
    except Exception:
        manager.disconnect(websocket)
        update_task.cancel()


async def send_updates(websocket: WebSocket):
    """Send periodic updates to a client."""
    db = get_db()
    last_log_id = 0

    try:
        while True:
            # Get new logs since last check
            logs = db.get_logs(limit=50)
            new_logs = [log for log in logs if log.id > last_log_id]

            if new_logs:
                last_log_id = max(log.id for log in new_logs)

                for log in reversed(new_logs):  # Send oldest first
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "log",
                                "data": {
                                    "id": log.id,
                                    "task_id": log.task_id,
                                    "level": log.level,
                                    "message": log.message,
                                    "details": log.get_details(),
                                    "created_at": log.created_at.isoformat()
                                    if log.created_at
                                    else None,
                                },
                            }
                        )
                    )

            # Send status update
            engine = get_engine()
            stats = engine.get_status()

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "status",
                        "data": {
                            "status": stats.status.value,
                            "pending_count": stats.pending_count,
                            "running_count": stats.running_count,
                            "completed_count": stats.completed_count,
                            "failed_count": stats.failed_count,
                            "total_processed": stats.total_processed,
                        },
                    }
                )
            )

            await asyncio.sleep(2)  # Update every 2 seconds

    except asyncio.CancelledError:
        pass
