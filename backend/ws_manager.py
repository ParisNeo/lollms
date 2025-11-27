# backend/ws_manager.py
import asyncio
import json
import os
import uuid
import datetime
import random
from typing import Dict, List, Set
from fastapi import WebSocket
from ascii_colors import trace_exception
from .db import session as db_session_module
from .db.models.broadcast import BroadcastMessage
from .db.models.connections import WebSocketConnection
from .db.models.user import User as DBUser, Friendship as DBFriendship
from .db.base import FriendshipStatus
from .session import user_sessions
from .settings import settings  # Import the global settings object

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
            print(f"INFO: User {user_id} connected via WebSocket (session: {session_id[:8]}). DB record created.")
            
            # --- Friend Connection Notification ---
            connecting_user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if connecting_user:
                friendships = db.query(DBFriendship).filter(
                    ((DBFriendship.user1_id == user_id) | (DBFriendship.user2_id == user_id)),
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
                    print(f"INFO: Queued 'friend_online' notifications for {len(friend_ids)} friends of user {user_id}.")
        except Exception as e:
            print(f"ERROR: Failed to create DB record or notify friends for WebSocket connection: {e}")
            if db: db.rollback()
        finally:
            if db: db.close()

    def disconnect(self, user_id: int, websocket: WebSocket):
        session_id = getattr(websocket, 'session_id', None)
        
        if user_id in self.active_connections and session_id in self.active_connections[user_id]:
            del self.active_connections[user_id][session_id]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                self.admin_user_ids.discard(user_id) # Also unregister admin if last connection is gone
        
        if session_id:
            db = None
            try:
                db = db_session_module.SessionLocal()
                db.query(WebSocketConnection).filter(WebSocketConnection.session_id == session_id).delete()
                
                user = db.query(DBUser).filter(DBUser.id == user_id).first()
                if user:
                    user.last_activity_at = datetime.datetime.now(datetime.timezone.utc)

                db.commit()
                print(f"INFO: User {user_id} disconnected WebSocket (session: {session_id[:8]}). DB record removed and activity updated.")
            except Exception as e:
                print(f"ERROR: Failed to process disconnect for WebSocket connection: {e}")
                if db: db.rollback()
            finally:
                if db: db.close()

    def register_admin(self, user_id: int):
        self.admin_user_ids.add(user_id)
        print(f"INFO: Admin user {user_id} registered. Total admins in this worker: {len(self.admin_user_ids)}")

    def unregister_admin(self, user_id: int):
        self.admin_user_ids.discard(user_id)
        print(f"INFO: Admin user {user_id} unregistered. Total admins in this worker: {len(self.admin_user_ids)}")

    async def send_personal_message(self, message_data: dict, user_id: int):
        if user_id in self.active_connections:
            sockets_to_remove = set()
            for websocket in list(self.active_connections[user_id].values()):
                try:
                    await websocket.send_json(message_data)
                except Exception as e:
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
        if not connected_admins: return
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
            print(f"ERROR: Failed to put message on DB broadcast queue in worker {os.getpid()}: {e}")
            if db: db.rollback()
        finally:
            if db: db.close()
    
    def broadcast_sync(self, message_data: dict):
        self._put_on_db_queue(message_data)

    def send_personal_message_sync(self, message_data: dict, user_id: int):
        self.broadcast_sync({"type": "personal", "user_id": user_id, "data": message_data})

    def broadcast_to_admins_sync(self, message_data: dict):
        self.broadcast_sync({"type": "admins", "data": message_data})

    def broadcast_internal_event_sync(self, event_type: str, data: dict):
        self.broadcast_sync({"type": "internal_event", "event_type": event_type, "data": data})

manager = ConnectionManager()

async def listen_for_broadcasts():
    print(f"INFO: Worker {os.getpid()} starting DB broadcast listener.")
    last_processed_id = 0
    while True:
        try:
            # Poll frequently for near-realtime updates (0.1s)
            await asyncio.sleep(0.1)
            
            db: Session = db_session_module.SessionLocal()
            try:
                if last_processed_id == 0:
                    last_message = db.query(BroadcastMessage).order_by(BroadcastMessage.id.desc()).first()
                    if last_message: last_processed_id = last_message.id

                messages = db.query(BroadcastMessage).filter(BroadcastMessage.id > last_processed_id).order_by(BroadcastMessage.id.asc()).limit(100).all()

                for msg in messages:
                    last_processed_id = msg.id
                    payload = msg.payload
                    
                    # --- INTERNAL EVENT HANDLING (NOT FORWARDED TO CLIENTS) ---
                    if payload.get("type") == "internal_event":
                        if payload.get("event_type") == "user_cache_invalidate":
                            username = payload.get("data", {}).get("username")
                            if username in user_sessions:
                                user_sessions[username]['lollms_clients_cache'] = {}
                                print(f"INFO: Worker {os.getpid()} invalidated client cache for user {username}")
                        continue # Skip to next message

                    # --- SETTINGS UPDATE HANDLING (INTERNAL & FORWARD) ---
                    if payload.get("type") == "settings_updated":
                        print(f"INFO: Worker {os.getpid()} received settings update notification. Refreshing settings cache.")
                        refresh_db = db_session_module.SessionLocal()
                        try:
                            settings.refresh(refresh_db)
                        finally:
                            refresh_db.close()
                        # Proceed to broadcast this to clients so they can update their UI state

                    # --- FORWARDING TO CLIENTS ---
                    if payload.get("type") == "personal":
                        user_id = payload.get("user_id")
                        if user_id is not None:
                            await manager.send_personal_message(payload.get("data"), user_id)
                    elif payload.get("type") == "admins":
                        await manager.broadcast_to_admins(payload.get("data"))
                    else: # Default to broadcast to everyone
                        await manager.broadcast(payload)
                
                # Cleanup old messages periodically
                if random.random() < 0.05:
                    one_minute_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
                    db.query(BroadcastMessage).filter(BroadcastMessage.created_at < one_minute_ago).delete(synchronize_session=False)
                    db.commit()

            finally:
                db.close()
        except asyncio.CancelledError:
            print(f"INFO: Broadcast listener task in worker {os.getpid()} cancelled.")
            break
        except Exception as e:
            print(f"ERROR: Error in broadcast listener loop (worker {os.getpid()}): {e}")
            trace_exception(e)
            await asyncio.sleep(1) # Wait a bit longer after an error before retrying
