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
        self.is_ready = False # Guard for startup sync storms
        
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
            
            connecting_user = db.query(DBUser).filter(DBUser.id == user_id).first()
            if connecting_user:
                if connecting_user.is_admin:
                    self.register_admin(user_id)

                db.commit()

                # --- CLIENT WARMUP WITH PROGRESS STREAMING ---
                def init_callback(text, msg_type, meta):
                    # We pipe progress messages directly to the user's socket
                    self.send_personal_message_sync({
                        "type": "init_progress",
                        "data": {
                            "message": text,
                            "is_error": msg_type == 24 # MSG_TYPE_ERROR = 24
                        }
                    }, user_id)
                    return True

                from backend.session import build_lollms_client_from_params
                # Trigger warmup in background
                threading.Thread(
                    target=build_lollms_client_from_params, 
                    args=(connecting_user.username,), 
                    kwargs={'callback': init_callback},
                    daemon=True
                ).start()

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
            print(f"ERROR: Failed to create DB record or register user: {e}")
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

    async def disconnect_user(self, user_id: int):
        """Closes all active WebSockets for a specific user."""
        if user_id in self.active_connections:
            # Copy items to avoid modification during iteration
            sessions = list(self.active_connections[user_id].values())
            for websocket in sessions:
                try:
                    await websocket.close(code=1000, reason="Disconnected by administrator")
                except Exception:
                    pass
                self.disconnect(user_id, websocket)

    def disconnect_user_sync(self, user_id: int):
        """Synchronous wrapper to trigger user disconnection across the cluster."""
        self.broadcast_sync({"type": "internal_event", "event_type": "user_disconnect", "data": {"user_id": user_id}})

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
            event_type = payload.get("event_type")
            data = payload.get("data", {})
            
            if event_type == "user_cache_invalidate":
                username = data.get("username")
                if username in user_sessions:
                    user_sessions[username]['lollms_clients_cache'] = {}
            
            elif event_type == "user_disconnect":
                user_id = data.get("user_id")
                if user_id:
                    await self.disconnect_user(int(user_id))
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
            print(f"ERROR: Failed to route push broadcast payload from hub: {e}")

    def broadcast_sync(self, message_data: dict):
        """
        Broadcasts a message across the worker cluster.
        STRICT SIZE GUARD: Prevents browser STATUS_BREAKPOINT crashes.
        """
        if not self.is_ready or not isinstance(message_data, dict):
            return

        # --- CRITICAL FRONTEND PROTECTION TEST ---
        try:
            # Prepare the JSON string to measure exact payload size
            payload_json = json.dumps(message_data)
            payload_size = len(payload_json)
            
            # 1MB Hard Limit. Chromium browsers crash when the heap is flooded 
            # with large objects via WebSockets during high-frequency updates.
            if payload_size > 1048576: 
                msg_type = message_data.get("type", "unknown")
                # Extract diagnostics to help developers find the source of the bloat
                bloated_fields = []
                if "data" in message_data and isinstance(message_data["data"], dict):
                    for k, v in message_data["data"].items():
                        s = len(json.dumps(v))
                        if s > 102400: # 100KB
                            bloated_fields.append(f"{k}: {s//1024}KB")
                
                ASCIIColors.warning(f"⚠️  DROPPED PAYLOAD [{msg_type}]: {payload_size//1024}KB. Bloat: {', '.join(bloated_fields)}")
                return # DROP THE MESSAGE
        except Exception:
            # If we can't even JSON encode it, it's definitely too dangerous to send
            return
        try:
            encoded_payload = json.dumps(message_data)
            encoded_len = len(encoded_payload)
            if encoded_len > 1024 * 1024:
                # Gather detailed statistics about the payload
                msg_type = type(message_data).__name__
                key_count = len(message_data.keys()) if isinstance(message_data, dict) else 'N/A'

                # Create a safe snapshot (first 500 chars, escaped)
                snapshot = repr(encoded_payload[:500])

                # Calculate size breakdown if dict
                size_breakdown = {}
                if isinstance(message_data, dict):
                    for k, v in message_data.items():
                        try:
                            size_breakdown[k] = len(json.dumps({k: v}))
                        except Exception:
                            size_breakdown[k] = 'unmeasurable'
                    top_heavy = sorted(size_breakdown.items(), key=lambda x: x[1] if isinstance(x[1], int) else 0, reverse=True)[:3]
                    top_keys_str = ', '.join([f"{k}={v}b" for k, v in top_heavy])
                else:
                    top_keys_str = 'N/A (not a dict)'

                # Build warning panel
                panel_content = (
                    f"\n{'='*60}\n"
                    f"  WEBSOCKET PAYLOAD TOO LARGE - DROPPED TO PROTECT UI\n"
                    f"{'='*60}\n"
                    f"  Total Size:        {encoded_len:,} bytes ({encoded_len/1024/1024:.2f} MB)\n"
                    f"  Limit:             {1024*1024:,} bytes (1.0 MB)\n"
                    f"  Data Type:         {msg_type}\n"
                    f"  Top-Level Keys:    {key_count}\n"
                    f"  Top 3 Heavy Keys:  {top_keys_str}\n"
                    f"{'-'*60}\n"
                    f"  Payload Snapshot (first 500 chars):\n"
                    f"  {snapshot}\n"
                    f"{'='*60}"
                )
                ASCIIColors.warning(panel_content)
                return
        except Exception as e:
            ASCIIColors.warning(f"WS Safety Check failed with error: {e}")
            pass
        
        # DEBUG LOGGING: Use this to see the "Storm" in your terminal
        msg_type = message_data.get("type")
        if msg_type == "personal":
            inner_type = message_data.get("data", {}).get("type", "unknown")
            ASCIIColors.debug(f"[WS-SEND] -> User {message_data.get('user_id')}: {inner_type}")
        else:
            ASCIIColors.debug(f"[WS-SEND] -> Global: {msg_type}")

        message_data["_pid"] = os.getpid()

        if self._loop and self._loop.is_running():
            async def dispatch():
                # [FIX] Wrap local delivery in try-except so it doesn't block Hub propagation
                try:
                    # 1. Local delivery (this worker instance)
                    msg_type = message_data.get("type")
                    if msg_type == "personal":
                        uid = message_data.get("user_id")
                        if uid is not None: await self.send_personal_message(message_data.get("data"), uid)
                    elif msg_type == "admins":
                        await self.broadcast_to_admins(message_data.get("data"))
                    else:
                        await self.broadcast(message_data)
                except Exception as e:
                    print(f"ERROR: Local WebSocket delivery failed, proceeding to Hub sync: {e}")
                
                # 2. Push to Communication Hub (cross-worker synchronization)
                # Rely on hub_writer availability rather than just worker count check
                if self.hub_writer:
                    try:
                        encoded = json.dumps(message_data).encode('utf-8')
                        packet = struct.pack('!I', len(encoded)) + encoded
                        self.hub_writer.write(packet)
                        await self.hub_writer.drain()
                    except Exception:
                        self.hub_writer = None
                        self.is_hub_connected = False
            
            asyncio.run_coroutine_threadsafe(dispatch(), self._loop)

        # Persistence to DB as a fallback log for multi-worker synchronization audit
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
            print(f"INFO: Worker {os.getpid()} successfully connected to Communication Hub.")
            
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
