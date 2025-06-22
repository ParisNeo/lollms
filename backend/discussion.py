# backend/discussion.py (Final Hybrid Version)

# --- Standard Library Imports ---
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any, Union
import datetime
from dataclasses import dataclass, field as dataclass_field
import uuid
# --- Third-Party Imports ---
from lollms_client import LollmsClient, LollmsDataManager, LollmsDiscussion

# --- Local Application Imports ---
# We keep this section very clean to avoid circular imports.
# The functions below will get their dependencies from other modules when called.
from backend.session import user_sessions, get_user_data_root, get_user_lollms_client


# ==================================================================================
# SECTION 1: LEGACY CODE - MODIFIED FOR MIGRATION
# This code is ONLY used by the migration script in main.py.
# It is designed to have no problematic internal imports.
# ==================================================================================

@dataclass
class _LegacyMessage:
    """A private, legacy message class for loading from YAML during migration."""
    sender: str
    sender_type: str
    content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None  # Correct attribute name for consistency
    created_at: datetime.datetime = dataclass_field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    sources: Optional[List[Dict]] = None
    steps: Optional[List[Dict]] = None
    image_references: Optional[List[str]] = dataclass_field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "_LegacyMessage":
        """Loads from a dictionary, mapping old key to new attribute name."""
        created_at_val = data.get("created_at")
        if isinstance(created_at_val, str):
            try: created_at = datetime.datetime.fromisoformat(created_at_val)
            except ValueError: created_at = datetime.datetime.now(datetime.timezone.utc)
        else: created_at = datetime.datetime.now(datetime.timezone.utc)
        
        sender = data.get("sender", "unknown")
        sender_type = data.get("sender_type", "user" if sender not in ["lollms", "assistant"] else "assistant")

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            sender=sender,
            sender_type=sender_type,
            content=data.get("content", ""),
            # FIX: Read from the old key name 'parent_message_id' from the YAML file
            parent_id=data.get("parent_message_id"), 
            created_at=created_at,
            binding_name=data.get("binding_name"),
            model_name=data.get("model_name"),
            token_count=data.get("token_count"),
            sources=data.get("sources",[]),
            steps=data.get("steps",[]),
            image_references=data.get("image_references", [])
        )

class LegacyDiscussion:
    """A private, legacy discussion class for loading YAML files during migration."""
    def __init__(self, discussion_id: Optional[str] = None, title: Optional[str] = None):
        self.messages: List[_LegacyMessage] = []
        self.discussion_id: str = discussion_id or str(uuid.uuid4())
        self.title: str = title or f"Imported {self.discussion_id[:8]}"
        self.rag_datastore_ids: Optional[str] = None
        self.active_branch_id: Optional[str] = None

    @staticmethod
    def load_from_yaml(file_path: Union[str, Path]) -> Optional["LegacyDiscussion"]:
        actual_path = Path(file_path)
        if not actual_path.exists(): return None
        try:
            with open(actual_path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file)
        except Exception:
            return None

        if not isinstance(data, dict):
            discussion = LegacyDiscussion(discussion_id=actual_path.stem)
            if isinstance(data, list):
                for msg_data in data:
                    if isinstance(msg_data, dict):
                        discussion.messages.append(_LegacyMessage.from_dict(msg_data))
            return discussion

        discussion = LegacyDiscussion(
            discussion_id=data.get("discussion_id", actual_path.stem),
            title=data.get("title")
        )
        discussion.rag_datastore_ids = data.get("rag_datastore_ids")
        discussion.active_branch_id = data.get("active_branch_id")
        
        for msg_data in data.get("messages", []):
            if isinstance(msg_data, dict):
                discussion.messages.append(_LegacyMessage.from_dict(msg_data))
        return discussion

# ==================================================================================
# SECTION 2: NEW DATABASE-DRIVEN CODE (Permanent)
# ==================================================================================

def get_user_discussion_manager(username: str) -> LollmsDataManager:
    """Retrieves or creates a LollmsDataManager instance for a specific user."""
    if "discussion_manager" in user_sessions.get(username, {}):
        manager = user_sessions[username].get("discussion_manager")
        if manager:
            return manager

    user_data_path = get_user_data_root(username)
    db_path = user_data_path / "discussions.db"
    db_url = f"sqlite:///{db_path.resolve()}"
    manager = LollmsDataManager(db_path=db_url)
    
    if username in user_sessions:
        user_sessions[username]["discussion_manager"] = manager
    else:
        user_sessions[username] = {"discussion_manager": manager}
    return manager

def get_user_discussion(username: str, discussion_id: str, create_if_missing: bool = False) -> Optional[LollmsDiscussion]:
    """Gets a specific discussion object for a user from their database."""
    lc = get_user_lollms_client(username)
    dm = get_user_discussion_manager(username)
    discussion = dm.get_discussion(lollms_client=lc, discussion_id=discussion_id, autosave=True)
    
    if discussion:
        return discussion
    elif create_if_missing:
        new_discussion = LollmsDiscussion.create_new(
            lollms_client=lc, db_manager=dm, id=discussion_id,
            autosave=True,
            discussion_metadata={"title": f"New Discussion {discussion_id[:8]}"},
        )
        return new_discussion
    return None