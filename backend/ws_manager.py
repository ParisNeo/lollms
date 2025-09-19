import asyncio
from typing import Dict, Set, Any
from fastapi import WebSocket
import json
import logging
from multiprocessing import Queue
from queue import Empty

logger = logging.getLogger("uvicorn.info")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.admin_user_ids: Set[int] = set()
        self._loop: asyncio.AbstractEventLoop = None
        self.broadcast_queue: Queue = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def set_broadcast_queue(self, queue: Queue):
        self.broadcast_queue = queue

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

    # --- Sync wrappers that put messages on the multiprocessing queue ---
    def _put_on_queue(self, payload: dict):
        if self.broadcast_queue:
            try:
                self.broadcast_queue.put_nowait(json.dumps(payload))
            except Exception as e:
                logger.error(f"Failed to put message on broadcast queue: {e}")
        else:
            logger.warning("Broadcast queue is not initialized. Message dropped.")

    def broadcast_sync(self, message_data: dict):
        payload = {"type": "broadcast", "data": message_data}
        self._put_on_queue(payload)

    def send_personal_message_sync(self, message_data: dict, user_id: int):
        payload = {"type": "personal", "user_id": user_id, "data": message_data}
        self._put_on_queue(payload)

    def broadcast_to_admins_sync(self, message_data: dict):
        payload = {"type": "admins", "data": message_data}
        self._put_on_queue(payload)

manager = ConnectionManager()

async def listen_for_broadcasts():
    """
    Listens for messages on the shared queue and dispatches them.
    This runs in each worker process's event loop.
    """
    logger.info(f"Worker {os.getpid()} starting broadcast listener.")
    while True:
        try:
            while not manager.broadcast_queue.empty():
                try:
                    message_str = manager.broadcast_queue.get_nowait()
                    payload = json.loads(message_str)
                    broadcast_type = payload.get("type")
                    data = payload.get("data")
                    
                    if broadcast_type == "broadcast":
                        await manager.broadcast(data)
                    elif broadcast_type == "admins":
                        await manager.broadcast_to_admins(data)
                    elif broadcast_type == "personal":
                        user_id = payload.get("user_id")
                        if user_id:
                            await manager.send_personal_message(data, user_id)
                except Empty:
                    continue # No more messages for now
                except Exception as e:
                    logger.error(f"Error processing message from queue: {e}")
            
            await asyncio.sleep(0.1) # Prevent a tight loop from consuming 100% CPU
        except asyncio.CancelledError:
            logger.info("Broadcast listener task cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in broadcast listener loop: {e}")
            await asyncio.sleep(1) # Wait a bit before retrying on major error