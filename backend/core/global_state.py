# backend/core/global_state.py
import threading
from typing import Dict, Any

# --- Global User Session Management & Locks ---
user_sessions: Dict[str, Dict[str, Any]] = {}
message_grade_lock = threading.Lock()