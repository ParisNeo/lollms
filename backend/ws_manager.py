import asyncio
from typing import Dict, Set, Any
from fastapi import WebSocket
import json
import logging
import os
from ascii_colors import trace_exception
from .db import session as db_session_module
from .db.models.broadcast import BroadcastMessage

logger = logging.getLogger("uvicorn.info")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.admin_user_ids: Set[int] = set()
        self._loop: asyncio.AbstractEventLoop = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected via WebSocket. Total connections for user: {len(self.active_connections[user_id])}")

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected one WebSocket. Connections remaining for user: {len(self.active_connections.get(user_id, set()))}")

    def register_admin(self, user_id: int):
        self.admin_user_ids.add(user_id)
        logger.info(f"Admin user {user_id} registered for notifications. Total admins: {len(self.admin_user_ids)}")

    def unregister_admin(self, user_id: int):
        self.admin_user_ids.discard(user_id)
        logger.info(f"Admin user {user_id} unregistered from notifications. Total admins: {len(self.admin_user_ids)}")

    async def send_personal_message(self, message_data: dict, user_id: int):
        if user_id in self.active_connections:
            sockets_to_remove = set()
            # Iterate over a copy of the set to allow modification during iteration
            for websocket in list(self.active_connections[user_id]):
                try:
                    await websocket.send_json(message_data)
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message to user {user_id} on a connection: {e}")
                    sockets_to_remove.add(websocket)
            
            # Clean up disconnected sockets for this user
            for websocket in sockets_to_remove:
                self.disconnect(user_id, websocket)

    async def broadcast(self, message_data: dict):
        users_to_cleanup = {}
        for user_id, sockets in list(self.active_connections.items()):
            for websocket in list(sockets):
                try:
                    await websocket.send_json(message_data)
                except Exception:
                    if user_id not in users_to_cleanup:
                        users_to_cleanup[user_id] = set()
                    users_to_cleanup[user_id].add(websocket)
        
        for user_id, sockets_to_remove in users_to_cleanup.items():
            for websocket in sockets_to_remove:
                self.disconnect(user_id, websocket)

    async def broadcast_to_admins(self, message_data: dict):
        connected_admins = [uid for uid in self.admin_user_ids if uid in self.active_connections]
        if not connected_admins:
            return

        for user_id in connected_admins:
            await self.send_personal_message(message_data, user_id)

    def _put_on_db_queue(self, payload: dict):
        db = None
        try:
            db = db_session_module.SessionLocal()
            db_message = BroadcastMessage(payload=payload)
            db.add(db_message)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to put message on DB broadcast queue: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()

    def broadcast_sync(self, message_data: dict):
        payload = {"type": "broadcast", "data": message_data}
        self._put_on_db_queue(payload)

    def send_personal_message_sync(self, message_data: dict, user_id: int):
        payload = {"type": "personal", "user_id": user_id, "data": message_data}
        self._put_on_db_queue(payload)

    def broadcast_to_admins_sync(self, message_data: dict):
        payload = {"type": "admins", "data": message_data}
        self._put_on_db_queue(payload)

manager = ConnectionManager()

async def listen_for_broadcasts():
    logger.info(f"Worker {os.getpid()} starting DB broadcast listener.")
    last_id_processed = 0
    while True:
        try:
            db = None
            try:
                db = db_session_module.SessionLocal()
                messages = db.query(BroadcastMessage).filter(BroadcastMessage.id > last_id_processed).order_by(BroadcastMessage.id).limit(100).all()
                if messages:
                    for message in messages:
                        try:
                            payload = message.payload
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
                            
                            last_id_processed = message.id
                        except Exception as e:
                            logger.error(f"Error processing message from DB queue (ID: {message.id}): {e}")
                    
                    db.query(BroadcastMessage).filter(BroadcastMessage.id <= last_id_processed).delete(synchronize_session=False)
                    db.commit()
            finally:
                if db:
                    db.close()
            
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            logger.info("Broadcast listener task cancelled.")
            break
        except Exception as e:
            trace_exception(e)
            logger.error(f"Error in broadcast listener loop: {e}")
            await asyncio.sleep(1)