# backend/ws_manager.py
import asyncio
import json
import os
import uuid
import datetime
import random
from typing import Dict, List, Set
from fastapi import WebSocket
from ascii_colors import trace_exception, ASCIIColors
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
        self.cleanup_tasks: Dict[int, asyncio.Task] = {} # {user_id: Task}

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        session_id = str(uuid.uuid4())
        websocket.session_id = session_id  # Attach session_id to the websocket object
        
        # If there's a pending cleanup for this user, cancel it (user reconnected)
        if user_id in self.cleanup_tasks:
            ASCIIColors.info(f"User {user_id} reconnected. Cancelling session cleanup.")
            self.cleanup_tasks[user_id].cancel()
            del self.cleanup_tasks[user_id]
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        self.active_connections[user_id][session_id] = websocket

        db = None
        try:
            db = db_session_module.SessionLocal()
            new_connection = WebSocketConnection(user_id=user_id, session_id=session_id)
            db.add(new_connection)
            db.commit()
            # print(f"INFO: User {user_id} connected via WebSocket (session: {session_id[:8]}). DB record created.")
            
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
                    # print(f"INFO: Queued 'friend_online' notifications for {len(friend_ids)} friends of user {user_id}.")
        except Exception as e:
            print(f"ERROR: Failed to create DB record or notify friends for WebSocket connection: {e}")
            if db: db.rollback()
        finally:
            if db: db.close()

    async def _delayed_cleanup(self, user_id: int):
        """Waits for a short period before clearing the user session to allow for page reloads."""
        try:
            # Wait 10 seconds. If user reconnects in this time, this task is cancelled.
            await asyncio.sleep(10)
            
            db = db_session_module.SessionLocal()
            try:
                user = db.query(DBUser).filter(DBUser.id == user_id).first()
                if user and user.username in user_sessions:
                    # 1. Close/Cleanup any specific resources if necessary
                    # 2. Delete the session entry
                    del user_sessions[user.username]
                    ASCIIColors.yellow(f"INFO: Session cache cleared for user '{user.username}' after disconnection timeout.")
            finally:
                db.close()
                
            if user_id in self.cleanup_tasks:
                del self.cleanup_tasks[user_id]
                
        except asyncio.CancelledError:
            # Task was cancelled because user reconnected
            pass
        except Exception as e:
            print(f"ERROR: Error in delayed cleanup for user {user_id}: {e}")

    def disconnect(self, user_id: int, websocket: WebSocket):
        session_id = getattr(websocket, 'session_id', None)
        
        all_connections_closed = False

        if user_id in self.active_connections and session_id in self.active_connections[user_id]:
            del self.active_connections[user_id][session_id]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                self.admin_user_ids.discard(user_id) # Also unregister admin if last connection is gone
                all_connections_closed = True
        
        if session_id:
            db = None
            try:
                db = db_session_module.SessionLocal()
                db.query(WebSocketConnection).filter(WebSocketConnection.session_id == session_id).delete()
                
                user = db.query(DBUser).filter(DBUser.id == user_id).first()
                if user:
                    user.last_activity_at = datetime.datetime.now(datetime.timezone.utc)
                    
                    # --- SCHEDULED CACHE CLEANUP ---
                    # Instead of clearing immediately, schedule a cleanup task.
                    if all_connections_closed:
                        # Cancel existing cleanup task if any (though shouldn't be one if we just closed last connection)
                        if user_id in self.cleanup_tasks:
                             self.cleanup_tasks[user_id].cancel()
                        
                        # Create new cleanup task using the stored loop or asyncio.create_task
                        # We use asyncio.create_task which attaches to the running loop
                        task = asyncio.create_task(self._delayed_cleanup(user_id))
                        self.cleanup_tasks[user_id] = task
                        ASCIIColors.info(f"User {user_id} disconnected completely. Scheduled session cleanup in 10s.")

                db.commit()
                # print(f"INFO: User {user_id} disconnected WebSocket (session: {session_id[:8]}). DB record removed and activity updated.")
            except Exception as e:
                print(f"ERROR: Failed to process disconnect for WebSocket connection: {e}")
                if db: db.rollback()
            finally:
                if db: db.close()

    def register_admin(self, user_id: int):
        self.admin_user_ids.add(user_id)
        # print(f"INFO: Admin user {user_id} registered. Total admins in this worker: {len(self.admin_user_ids)}")

    def unregister_admin(self, user_id: int):
        self.admin_user_ids.discard(user_id)
        # print(f"INFO: Admin user {user_id} unregistered. Total admins in this worker: {len(self.admin_user_ids)}")

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
        """
        Sends a broadcast message.
        Optimized to send immediately to local connections via the event loop,
        while also persisting to DB for other workers (and history/robustness).
        Tags the message with PID to prevent local double-sending.
        """
        if not isinstance(message_data, dict):
            return
        
        # Tag with PID
        message_data["_pid"] = os.getpid()

        # 1. Immediate Local Delivery (Fast Path)
        if self._loop and self._loop.is_running():
            async def local_dispatch():
                try:
                    msg_type = message_data.get("type")
                    if msg_type == "personal":
                        uid = message_data.get("user_id")
                        if uid is not None:
                            await self.send_personal_message(message_data.get("data"), uid)
                    elif msg_type == "admins":
                        await self.broadcast_to_admins(message_data.get("data"))
                    else:
                        # Standard broadcast
                        await self.broadcast(message_data)
                except Exception as e:
                    print(f"Error in local broadcast dispatch: {e}")

            # Schedule on the main event loop
            asyncio.run_coroutine_threadsafe(local_dispatch(), self._loop)

        # 2. Persist to DB (Slow Path / Cross-Worker)
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
    
    # Initialize last_processed_id to current max to avoid re-processing old messages on restart
    # Use a short-lived session for initialization
    init_db = db_session_module.SessionLocal()
    try:
        last_message = init_db.query(BroadcastMessage).order_by(BroadcastMessage.id.desc()).first()
        if last_message:
            last_processed_id = last_message.id
    except Exception as e:
        print(f"WARNING: Could not initialize broadcast listener ID: {e}")
    finally:
        init_db.close()
        
    while True:
        try:
            # Poll frequently for near-realtime updates (0.1s)
            await asyncio.sleep(0.1)
            
            db: Session = db_session_module.SessionLocal()
            try:
                # If we still haven't initialized (e.g. DB was empty before), try again inside loop logic
                # But querying simply > last_processed_id (which is 0) works fine if DB was empty.
                
                messages = db.query(BroadcastMessage).filter(BroadcastMessage.id > last_processed_id).order_by(BroadcastMessage.id.asc()).limit(100).all()

                for msg in messages:
                    last_processed_id = msg.id
                    payload = msg.payload
                    
                    # --- LOOPBACK PROTECTION ---
                    # If this message originated from THIS worker, it was already sent via broadcast_sync locally.
                    if payload.get("_pid") == os.getpid():
                        continue

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
                        # print(f"INFO: Worker {os.getpid()} received settings update notification. Refreshing settings cache.")
                        refresh_db = db_session_module.SessionLocal()
                        try:
                            settings.refresh(refresh_db)
                        finally:
                            refresh_db.close()
                        # Proceed to broadcast this to clients so they can update their UI state

                    # --- FORWARDING TO CLIENTS ---
                    try:
                        if payload.get("type") == "personal":
                            user_id = payload.get("user_id")
                            if user_id is not None:
                                await manager.send_personal_message(payload.get("data"), user_id)
                        elif payload.get("type") == "admins":
                            await manager.broadcast_to_admins(payload.get("data"))
                        else: # Default to broadcast to everyone
                            await manager.broadcast(payload)
                    except Exception as client_send_error:
                        print(f"ERROR: Failed to forward broadcast to clients: {client_send_error}")

                
                # Cleanup old messages periodically (every ~200 iterations approx 20s, with probability check)
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
