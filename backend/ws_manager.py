from typing import Dict
from fastapi import WebSocket
import json
import logging

# Set up a logger for connection events
logger = logging.getLogger("uvicorn.info")

class ConnectionManager:
    """Manages active WebSocket connections for real-time communication."""
    def __init__(self):
        # Maps user_id to their active WebSocket connection
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        """Accepts and stores a new websocket connection, overwriting any old one."""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"User {user_id} connected via WebSocket. Total connections: {len(self.active_connections)}")

    def disconnect(self, user_id: int):
        """Removes a websocket connection from the active pool."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected from WebSocket. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message_data: dict, user_id: int):
        """Sends a JSON message to a specific user if they are connected."""
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_json(message_data)
                logger.info(f"Sent WebSocket message to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send WebSocket message to user {user_id}: {e}")
                # Potentially disconnect a broken socket
                self.disconnect(user_id)

# Create a single instance of the manager to be used across the application.
# This singleton pattern ensures all parts of the app share the same connection pool.
manager = ConnectionManager()