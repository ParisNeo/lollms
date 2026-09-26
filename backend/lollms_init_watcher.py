# backend/lollms_init_watcher.py
from ascii_colors import ASCIIColors
import datetime

def lollms_init_watcher(msg, msg_type="info", metadata=None):
    """
    Watches background initialization and package installations, logging to console
    and broadcasting live progress to the frontend through WebSocket.
    """
    ASCIIColors.green(msg)
    try:
        from backend.ws_manager import manager
        clean_msg = str(msg).strip()
        if clean_msg:
            # 1. Update the live setup status banner in the Admin panel
            manager.broadcast_sync({
                "type": "binding_setup_status",
                "data": {
                    "message": clean_msg,
                    "type": msg_type or "info",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            })
            # 2. Emit temporary toast notification if it's a significant milestone
            if any(k in clean_msg.lower() for k in ["installing", "virtual environment", "spawning", "downloading", "creating"]):
                manager.broadcast_sync({
                    "type": "notification",
                    "data": {
                        "message": f"⚙️ {clean_msg}",
                        "type": "info",
                        "duration": 5000
                    }
                })
    except Exception:
        pass