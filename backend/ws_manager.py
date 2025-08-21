import asyncio
from typing import Dict, Set, Any
from fastapi import WebSocket
import json
import logging

# NEW IMPORTS
from backend.db import get_db
from backend.db.models.broadcast import BroadcastMessage

logger = logging.getLogger("uvicorn.info")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.admin_user_ids: Set[int] = set()
        self._loop: asyncio.AbstractEventLoop = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected via WebSocket. Total connections: {len(self.active_connections)}")

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected from WebSocket. Total connections: {len(self.active_connections)}")

    def register_admin(self, user_id: int):
        self.admin_user_ids.add(user_id)
        logger.info(f"Admin user {user_id} registered for notifications. Total admins: {len(self.admin_user_ids)}")

    def unregister_admin(self, user_id: int):
        self.admin_user_ids.discard(user_id)
        logger.info(f"Admin user {user_id} unregistered from notifications. Total admins: {len(self.admin_user_ids)}")

    async def send_personal_message(self, message_data: dict, user_id: int):
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_json(message_data)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message to user {user_id}: {e}")
                self.disconnect(user_id)

    async def broadcast(self, message_data: dict):
        disconnected_users = []
        # Create a copy of items to iterate over, as disconnect can modify the dict
        for user_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_json(message_data)
            except Exception:
                disconnected_users.append(user_id)
        
        for user_id in disconnected_users:
            self.disconnect(user_id)


    async def broadcast_to_admins(self, message_data: dict):
        connected_admins = [uid for uid in self.admin_user_ids if uid in self.active_connections]
        if not connected_admins:
            return

        for user_id in connected_admins:
            await self.send_personal_message(message_data, user_id)

    # --- Sync wrappers for calling async methods from sync threads (e.g., TaskManager) ---
    def _write_to_db_queue(self, payload: dict):
        db_session = None
        try:
            db_session = next(get_db())
            db_message = BroadcastMessage(payload=payload)
            db_session.add(db_message)
            db_session.commit()
        except Exception as e:
            logger.error(f"Failed to write broadcast message to database queue: {e}")
            if db_session:
                db_session.rollback()
        finally:
            if db_session:
                db_session.close()

    def broadcast_sync(self, message_data: dict):
        payload = {"type": "broadcast", "data": message_data}
        self._write_to_db_queue(payload)

    def send_personal_message_sync(self, message_data: dict, user_id: int):
        payload = {"type": "personal", "user_id": user_id, "data": message_data}
        self._write_to_db_queue(payload)

    def broadcast_to_admins_sync(self, message_data: dict):
        payload = {"type": "admins", "data": message_data}
        self._write_to_db_queue(payload)


manager = ConnectionManager()