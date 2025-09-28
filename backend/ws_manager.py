# backend/ws_manager.py
import asyncio
from typing import Dict, Set, Any
from fastapi import WebSocket
import json
import logging
import os
import uuid
import datetime
from ascii_colors import trace_exception
from .db import session as db_session_module
from .db.models.broadcast import BroadcastMessage
from .db.models.connections import WebSocketConnection
from .db.models.user import User as DBUser, Friendship as DBFriendship
from .db.base import FriendshipStatus
from .session import user_sessions

logger = logging.getLogger("uvicorn.info")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[str, WebSocket]] = {} # {user_id: {session_id: websocket}}
        self.admin_user_ids: Set[int] = set()
        self._loop: asyncio.AbstractEventLoop = None
        self.local_queue: asyncio.Queue = asyncio.Queue()

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        # Start a local consumer task for this worker's in-memory queue
        self._loop.create_task(self._local_queue_consumer())

    async def _local_queue_consumer(self):
        """Consumes messages from the in-memory queue for this worker."""
        logger.info(f"Worker {os.getpid()} starting local in-memory queue consumer.")
        while True:
            try:
                payload = await self.local_queue.get()
                broadcast_type = payload.get("type")
                data = payload.get("data")
                
                if broadcast_type == "broadcast":
                    await self.broadcast(data)
                elif broadcast_type == "admins":
                    await self.broadcast_to_admins(data)
                elif broadcast_type == "personal":
                    user_id = payload.get("user_id")
                    if user_id:
                        await self.send_personal_message(data, user_id)

                self.local_queue.task_done()
            except asyncio.CancelledError:
                logger.info(f"Local queue consumer in worker {os.getpid()} is shutting down.")
                break
            except Exception as e:
                logger.error(f"Error in local queue consumer for worker {os.getpid()}: {e}")
                trace_exception(e)

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        session_id = str(uuid.uuid4())
        websocket.session_id = session_id  # Attach session_id to the websocket object
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        self.active_connections[user_id][session_id] = websocket

        db = None
        try:
            db = db_session_module.SessionLocal()
            new_connection = WebSocketConnection(user_id=user_id, session_id=session_id)
            db.add(new_connection)
            db.commit()
            logger.info(f"User {user_id} connected via WebSocket (session: {session_id[:8]}). DB record created.")
            
            # --- NEW: Friend Connection Notification ---
            connecting_user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if connecting_user:
                # Find all accepted friendships for this user
                friendships = db.query(DBFriendship).filter(
                    (DBFriendship.user1_id == user_id) | (DBFriendship.user2_id == user_id),
                    DBFriendship.status == FriendshipStatus.ACCEPTED
                ).all()

                friend_ids = {f.user1_id if f.user2_id == user_id else f.user2_id for f in friendships}
                
                if friend_ids:
                    notification_payload = {
                        "type": "friend_online",
                        "data": {
                            "username": connecting_user.username,
                            "icon": connecting_user.icon
                        }
                    }
                    for friend_id in friend_ids:
                        # Use the synchronous method which queues the message for delivery
                        # This avoids awaiting in a sync context
                        self.send_personal_message_sync(notification_payload, friend_id)
                    logger.info(f"Queued 'friend_online' notifications for {len(friend_ids)} friends of user {user_id}.")
            # --- END NEW ---

        except Exception as e:
            logger.error(f"Failed to create DB record or notify friends for WebSocket connection: {e}")
            if db: db.rollback()
        finally:
            if db: db.close()

    def disconnect(self, user_id: int, websocket: WebSocket):
        session_id = getattr(websocket, 'session_id', None)
        
        if user_id in self.active_connections and session_id in self.active_connections[user_id]:
            del self.active_connections[user_id][session_id]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        if session_id:
            db = None
            try:
                db = db_session_module.SessionLocal()
                db.query(WebSocketConnection).filter(WebSocketConnection.session_id == session_id).delete()
                
                # --- NEW: Update last_activity_at on disconnect ---
                user = db.query(DBUser).filter(DBUser.id == user_id).first()
                if user:
                    user.last_activity_at = datetime.datetime.now(datetime.timezone.utc)
                # --- END NEW ---

                db.commit()
                logger.info(f"User {user_id} disconnected WebSocket (session: {session_id[:8]}). DB record removed and activity updated.")
            except Exception as e:
                logger.error(f"Failed to process disconnect for WebSocket connection: {e}")
                if db: db.rollback()
            finally:
                if db: db.close()

    def register_admin(self, user_id: int):
        self.admin_user_ids.add(user_id)
        logger.info(f"Admin user {user_id} registered for notifications. Total admins: {len(self.admin_user_ids)}")

    def unregister_admin(self, user_id: int):
        self.admin_user_ids.discard(user_id)
        logger.info(f"Admin user {user_id} unregistered from notifications. Total admins: {len(self.admin_user_ids)}")

    async def send_personal_message(self, message_data: dict, user_id: int):
        if user_id in self.active_connections:
            sockets_to_remove = set()
            for websocket in list(self.active_connections[user_id].values()):
                try:
                    await websocket.send_json(message_data)
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message to user {user_id} on a connection: {e}")
                    sockets_to_remove.add(websocket)
            
            for websocket in sockets_to_remove:
                self.disconnect(user_id, websocket)

    async def broadcast(self, message_data: dict):
        users_to_cleanup = {}
        for user_id, sockets_dict in list(self.active_connections.items()):
            for websocket in list(sockets_dict.values()):
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
            logger.error(f"Failed to put message on DB broadcast queue in worker {os.getpid()}: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
    
    def broadcast_sync(self, message_data: dict):
        payload = {"type": "broadcast", "data": message_data}
        self._put_on_db_queue(payload)

    def send_personal_message_sync(self, message_data: dict, user_id: int):
        if self._loop and user_id in self.active_connections:
            payload = {"type": "personal", "user_id": user_id, "data": message_data}
            self._loop.call_soon_threadsafe(self.local_queue.put_nowait, payload)
        else:
            payload = {"type": "personal", "user_id": user_id, "data": message_data}
            self._put_on_db_queue(payload)

    def broadcast_to_admins_sync(self, message_data: dict):
        payload = {"type": "admins", "data": message_data}
        is_any_admin_local = any(admin_id in self.active_connections for admin_id in self.admin_user_ids)
        if self._loop and is_any_admin_local:
            self._loop.call_soon_threadsafe(self.local_queue.put_nowait, payload)
        self._put_on_db_queue(payload)

    def broadcast_internal_event_sync(self, event_type: str, data: dict):
        """Puts an internal event on the DB queue for all workers to process."""
        payload = {"type": event_type, "data": data}
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
                            
                            if broadcast_type == "user_cache_invalidate":
                                username_to_invalidate = data.get("username")
                                if username_to_invalidate and username_to_invalidate in user_sessions:
                                    logger.info(f"Worker {os.getpid()} invalidating LollmsClient cache for user: {username_to_invalidate}")
                                    if "lollms_clients_cache" in user_sessions[username_to_invalidate]:
                                        user_sessions[username_to_invalidate]["lollms_clients_cache"] = {}
                            elif broadcast_type == "broadcast":
                                await manager.broadcast(data)
                            elif broadcast_type == "admins":
                                await manager.broadcast_to_admins(data)
                            elif broadcast_type == "personal":
                                user_id = payload.get("user_id")
                                if user_id and user_id in manager.active_connections:
                                    await manager.send_personal_message(data, user_id)
                            
                            last_id_processed = message.id
                        except Exception as e:
                            logger.error(f"Error processing message from DB queue (ID: {message.id}): {e}")
                    
                    db.query(BroadcastMessage).filter(BroadcastMessage.id <= last_id_processed).delete(synchronize_session=False)
                    db.commit()
            finally:
                if db:
                    db.close()
            
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Broadcast listener task cancelled.")
            break
        except Exception as e:
            trace_exception(e)
            logger.error(f"Error in broadcast listener loop: {e}")
            await asyncio.sleep(1)