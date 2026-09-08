"""WebSocket fan-out for live dashboard updates.

Event types: cyclone.detected, cyclone.updated, prediction.issued,
alert.issued, alert.acknowledged, pipeline.status. See docs/api-contract.md §1.
"""

from datetime import UTC, datetime

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, event_type: str, payload: dict) -> None:
        message = {
            "type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        for connection in list(self.active):
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                self.disconnect(connection)

    async def endpoint(self, websocket: WebSocket) -> None:
        await self.connect(websocket)
        try:
            while True:
                # Client messages are subscription hints; the server is push-driven.
                await websocket.receive_text()
        except WebSocketDisconnect:
            self.disconnect(websocket)


connection_manager = ConnectionManager()
