from typing import Dict, Set
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger("uvicorn.info")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.admin_user_ids: Set[int] = set()

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
                logger.debug(f"Sent WebSocket message to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send WebSocket message to user {user_id}: {e}")
                self.disconnect(user_id)

    async def broadcast_to_admins(self, message_data: dict):
        connected_admins = [uid for uid in self.admin_user_ids if uid in self.active_connections]
        if not connected_admins:
            logger.info("Broadcast to admins requested, but no admins are currently connected.")
            return

        logger.info(f"Broadcasting message to {len(connected_admins)} connected admins.")
        for user_id in connected_admins:
            await self.send_personal_message(message_data, user_id)

manager = ConnectionManager()