# [UPDATE] backend/ws_manager.py
import asyncio
from typing import Dict, Set, Any
from fastapi import WebSocket
import json
import logging
import os
import uuid
import datetime
import random
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

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

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
                
                user = db.query(DBUser).filter(DBUser.id == user_id).first()
                if user:
                    user.last_activity_at = datetime.datetime.now(datetime.timezone.utc)

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
        payload = {"type": "personal", "user_id": user_id, "data": message_data}
        self._put_on_db_queue(payload)

    def broadcast_to_admins_sync(self, message_data: dict):
        payload = {"type": "admins", "data": message_data}
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
                    
                    # Periodic cleanup instead of immediate deletion
                    if random.random() < 0.05: # Roughly every 20 polls
                        one_minute_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
                        db.query(BroadcastMessage).filter(BroadcastMessage.created_at < one_minute_ago).delete(synchronize_session=False)
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