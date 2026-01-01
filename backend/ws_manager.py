import asyncio
import json
import os
import uuid
import datetime
import random
import struct
import threading
from typing import Dict, List, Set, Optional
from fastapi import WebSocket
from ascii_colors import trace_exception, ASCIIColors
from .db import session as db_session_module
from .db.models.broadcast import BroadcastMessage
from .db.models.connections import WebSocketConnection
from .db.models.user import User as DBUser, Friendship as DBFriendship
from .db.base import FriendshipStatus
from .session import user_sessions
from .settings import settings
from backend.config import SERVER_CONFIG

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict[str, WebSocket]] = {} # {user_id: {session_id: websocket}}
        self.admin_user_ids: Set[int] = set()
        self._loop: asyncio.AbstractEventLoop = None
        self.cleanup_tasks: Dict[int, asyncio.Task] = {} # {user_id: Task}
        
        # Hub Client State
        self.hub_writer: Optional[asyncio.StreamWriter] = None
        self.is_hub_connected = False
        
        # Cache server config workers count for quick access
        self.workers_count = SERVER_CONFIG.get("workers", 1)

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        session_id = str(uuid.uuid4())
        websocket.session_id = session_id
        
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
            
            connecting_user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if connecting_user:
                # Warm up LollmsClient in a separate thread to avoid blocking WebSocket handshake
                # This ensures the client (and MCP connections) is ready when the UI requests it
                from backend.session import get_user_lollms_client
                threading.Thread(target=get_user_lollms_client, args=(connecting_user.username,), daemon=True).start()

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
        except Exception as e:
            print(f"ERROR: Failed to create DB record: {e}")
            if db: db.rollback()
        finally:
            if db: db.close()

    async def _delayed_cleanup(self, user_id: int):
        try:
            await asyncio.sleep(10)
            db = db_session_module.SessionLocal()
            try:
                user = db.query(DBUser).filter(DBUser.id == user_id).first()
                if user and user.username in user_sessions:
                    del user_sessions[user.username]
                    ASCIIColors.yellow(f"INFO: Session cache cleared for user '{user.username}' after disconnection timeout.")
            finally:
                db.close()
            if user_id in self.cleanup_tasks:
                del self.cleanup_tasks[user_id]
        except asyncio.CancelledError:
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
                self.admin_user_ids.discard(user_id)
                all_connections_closed = True
        
        if session_id:
            db = None
            try:
                db = db_session_module.SessionLocal()
                db.query(WebSocketConnection).filter(WebSocketConnection.session_id == session_id).delete()
                user = db.query(DBUser).filter(DBUser.id == user_id).first()
                if user:
                    user.last_activity_at = datetime.datetime.now(datetime.timezone.utc)
                    if all_connections_closed:
                        if user_id in self.cleanup_tasks:
                             self.cleanup_tasks[user_id].cancel()
                        task = asyncio.create_task(self._delayed_cleanup(user_id))
                        self.cleanup_tasks[user_id] = task
                        ASCIIColors.info(f"User {user_id} disconnected completely. Scheduled session cleanup in 10s.")
                db.commit()
            except Exception as e:
                print(f"ERROR: Failed to process disconnect: {e}")
                if db: db.rollback()
            finally:
                if db: db.close()

    def register_admin(self, user_id: int):
        self.admin_user_ids.add(user_id)

    def unregister_admin(self, user_id: int):
        self.admin_user_ids.discard(user_id)

    async def send_personal_message(self, message_data: dict, user_id: int):
        if user_id in self.active_connections:
            sockets_to_remove = set()
            for websocket in list(self.active_connections[user_id].values()):
                try:
                    await websocket.send_json(message_data)
                except Exception:
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

    async def _handle_broadcast_payload(self, payload: dict):
        """Processes incoming messages from the Com Hub push stream."""
        # Loopback protection
        if payload.get("_pid") == os.getpid():
            return

        # Internal synchronization events
        if payload.get("type") == "internal_event":
            if payload.get("event_type") == "user_cache_invalidate":
                username = payload.get("data", {}).get("username")
                if username in user_sessions:
                    user_sessions[username]['lollms_clients_cache'] = {}
            return

        # Global settings refresh
        if payload.get("type") == "settings_updated":
            refresh_db = db_session_module.SessionLocal()
            try:
                settings.refresh(refresh_db)
            finally:
                refresh_db.close()

        # Dispatch to local client WebSockets
        try:
            if payload.get("type") == "personal":
                uid = payload.get("user_id")
                if uid is not None:
                    await self.send_personal_message(payload.get("data"), uid)
            elif payload.get("type") == "admins":
                await self.broadcast_to_admins(payload.get("data"))
            else:
                await self.broadcast(payload)
        except Exception as e:
            print(f"ERROR: Failed to route push broadcast payload: {e}")

    def broadcast_sync(self, message_data: dict):
        """
        Broadcasts a message across the worker cluster.
        Pushes to local connections via the event loop and forwards to the Hub for other workers.
        """
        if not isinstance(message_data, dict):
            return
        
        message_data["_pid"] = os.getpid()

        if self._loop and self._loop.is_running():
            async def dispatch():
                # 1. Local delivery (this worker instance)
                msg_type = message_data.get("type")
                if msg_type == "personal":
                    uid = message_data.get("user_id")
                    if uid is not None: await self.send_personal_message(message_data.get("data"), uid)
                elif msg_type == "admins":
                    await self.broadcast_to_admins(message_data.get("data"))
                else:
                    await self.broadcast(message_data)
                
                # 2. Push to Communication Hub (cross-worker synchronization)
                # OPTIMIZATION: Only push to hub if running in multi-worker mode
                if self.workers_count > 1 and self.hub_writer:
                    try:
                        encoded = json.dumps(message_data).encode('utf-8')
                        packet = struct.pack('!I', len(encoded)) + encoded
                        self.hub_writer.write(packet)
                        await self.hub_writer.drain()
                    except Exception:
                        self.hub_writer = None
                        self.is_hub_connected = False
            
            asyncio.run_coroutine_threadsafe(dispatch(), self._loop)

        # Persistence to DB as a logging fallback (only in multi-worker mode)
        # In single worker mode, local delivery is enough and faster.
        if self.workers_count > 1:
            self._put_on_db_queue(message_data)

    def _put_on_db_queue(self, payload: dict):
        db = None
        try:
            db = db_session_module.SessionLocal()
            db_message = BroadcastMessage(payload=payload)
            db.add(db_message)
            db.commit()
        except Exception:
            if db: db.rollback()
        finally:
            if db: db.close()

    def send_personal_message_sync(self, message_data: dict, user_id: int):
        self.broadcast_sync({"type": "personal", "user_id": user_id, "data": message_data})

    def broadcast_to_admins_sync(self, message_data: dict):
        self.broadcast_sync({"type": "admins", "data": message_data})

    def broadcast_internal_event_sync(self, event_type: str, data: dict):
        self.broadcast_sync({"type": "internal_event", "event_type": event_type, "data": data})

manager = ConnectionManager()

async def listen_for_broadcasts():
    """
    Background worker task that maintains a persistent connection to the Hub.
    Replaces the previous database polling logic with event-driven pushes.
    """
    # Use dynamic setting with a fallback to the SERVER_CONFIG/default
    hub_port = settings.get("com_hub_port", SERVER_CONFIG.get("com_hub_port", 8042))
    print(f"INFO: Worker {os.getpid()} initializing Communication Hub client listener on port {hub_port}.")
    
    while True:
        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', hub_port)
            manager.hub_writer = writer
            manager.is_hub_connected = True
            
            while True:
                length_data = await reader.readexactly(4)
                length = struct.unpack('!I', length_data)[0]
                data = await reader.readexactly(length)
                payload = json.loads(data.decode('utf-8'))
                
                await manager._handle_broadcast_payload(payload)
                
        except (asyncio.IncompleteReadError, ConnectionRefusedError, ConnectionResetError, BrokenPipeError):
            manager.hub_writer = None
            manager.is_hub_connected = False
            await asyncio.sleep(2) # Backoff before retry
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Hub Client Error (Worker {os.getpid()}): {e}")
            await asyncio.sleep(5)
