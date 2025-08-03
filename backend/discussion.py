# backend/discussion.py

from pathlib import Path
from typing import List, Optional, Any
import datetime
import uuid
import yaml
from dataclasses import dataclass, field as dataclass_field
from lollms_client import LollmsClient, LollmsDataManager, LollmsDiscussion


from backend.session import user_sessions, get_user_data_root, get_user_lollms_client

@dataclass
class _LegacyMessage:
    sender: str
    sender_type: str
    content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    created_at: datetime.datetime = dataclass_field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    sources: Optional[List[Any]] = None
    steps: Optional[List[Any]] = None
    image_references: Optional[List[str]] = dataclass_field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "_LegacyMessage":
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
    def __init__(self, discussion_id: Optional[str] = None, title: Optional[str] = None):
        self.messages: List[_LegacyMessage] = []
        self.discussion_id: str = discussion_id or str(uuid.uuid4())
        self.title: str = title or f"Imported {self.discussion_id[:8]}"
        self.rag_datastore_ids: Optional[list] = None
        self.active_branch_id: Optional[str] = None

    @staticmethod
    def load_from_yaml(file_path: Path) -> Optional["LegacyDiscussion"]:
        if not file_path.exists(): return None
        try:
            with open(file_path, "r", encoding="utf-8") as file: data = yaml.safe_load(file)
        except Exception: return None

        if not isinstance(data, dict):
            discussion = LegacyDiscussion(discussion_id=file_path.stem)
            if isinstance(data, list):
                for msg_data in data:
                    if isinstance(msg_data, dict): discussion.messages.append(_LegacyMessage.from_dict(msg_data))
            return discussion

        discussion = LegacyDiscussion(discussion_id=data.get("discussion_id", file_path.stem), title=data.get("title"))
        discussion.rag_datastore_ids = data.get("rag_datastore_ids")
        discussion.active_branch_id = data.get("active_branch_id")
        
        for msg_data in data.get("messages", []):
            if isinstance(msg_data, dict): discussion.messages.append(_LegacyMessage.from_dict(msg_data))
        return discussion

def get_user_discussion_manager(username: str) -> LollmsDataManager:
    if "discussion_manager" in user_sessions.get(username, {}):
        manager = user_sessions[username].get("discussion_manager")
        if manager: return manager

    user_data_path = get_user_data_root(username)
    db_path = user_data_path / "discussions.db"
    db_url = f"sqlite:///{db_path.resolve()}"
    manager = LollmsDataManager(db_path=db_url)
    
    if username in user_sessions:
        user_sessions[username]["discussion_manager"] = manager
    else:
        user_sessions[username] = {"discussion_manager": manager}
    return manager

def get_user_discussion(username: str, discussion_id: str, create_if_missing: bool = False, lollms_client: Optional[LollmsClient] = None) -> Optional[LollmsDiscussion]:
    # If no client is passed, create one using the user's current settings.
    # This is the key change to ensure the correct context size and model are always used.
    lc = lollms_client if lollms_client is not None else get_user_lollms_client(username)
    dm = get_user_discussion_manager(username)
    
    # Extract max_context_size from the definitive LollmsClient instance (lc).
    
    max_context_size = lc.get_ctx_size() or 4096
    
    discussion = dm.get_discussion(
        lollms_client=lc,
        discussion_id=discussion_id,
        max_context_size=max_context_size,
        autosave=True
    )
    
    if discussion:
        discussion.lollms_client = lc
        discussion.max_context_size = max_context_size  # Ensure it's correctly set on existing discussions

        # --- FIX: In-place migration for legacy discussion_images format ---
        if discussion.metadata and 'discussion_images' in discussion.metadata:
            images_data = discussion.metadata['discussion_images']
            # Check if migration is needed (if it is a list, not a dict with 'data' key)
            if isinstance(images_data, list):
                print(f"INFO: Migrating legacy image format for discussion {discussion_id}")
                
                # Handle list of strings (oldest format) or list of dicts (intermediate format)
                image_list = []
                active_list = []
                for item in images_data:
                    if isinstance(item, dict) and 'image' in item:
                        image_list.append(item['image'])
                        active_list.append(item.get('active', True))
                    elif isinstance(item, str):
                        image_list.append(item)
                        active_list.append(True)

                new_images_format = {
                    'data': image_list,
                    'active': active_list
                }
                discussion.set_metadata_item('discussion_images', new_images_format)
                # The object in memory now has the old format. We need to update it.
                discussion.images = new_images_format['data']
                discussion.active_images = new_images_format['active']
        return discussion
    elif create_if_missing:
        new_discussion = LollmsDiscussion.create_new(
            lollms_client=lc,
            db_manager=dm,
            id=discussion_id,
            max_context_size=max_context_size,
            autosave=True,
            discussion_metadata={"title": f"New Discussion {discussion_id[:8]}"},
        )
        return new_discussion
    return None