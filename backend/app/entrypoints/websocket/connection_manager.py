from typing import Dict
from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):
        self.active: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        # If a connection already exists for this session_id, close it to prevent
        # stale handlers from competing with the new one (reconnect race condition).
        old_ws = self.active.get(session_id)
        if old_ws is not None and old_ws is not ws:
            try:
                await old_ws.close(code=4000, reason="superseded_by_new_connection")
            except Exception:
                pass
            self.active.pop(session_id, None)
        await ws.accept()
        self.active[session_id] = ws

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)

    async def send_json(self, session_id: str, payload: dict):
        ws = self.active.get(session_id)
        if ws:
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(session_id)

    async def send_bytes(self, session_id: str, data: bytes):
        ws = self.active.get(session_id)
        if ws:
            try:
                await ws.send_bytes(data)
            except Exception:
                self.disconnect(session_id)


manager = ConnectionManager()
