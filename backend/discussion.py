# --- Helpers ---
# Standard Library Imports
import os
import shutil
import uuid
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, cast, Union, Tuple, AsyncGenerator
import datetime
import asyncio
import threading
import traceback
import base64

# Third-Party Imports
import toml
import yaml
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    File,
    UploadFile,
    Form,
    APIRouter,
    Response,
    Query,
    BackgroundTasks
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr, field_validator, validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import (
    or_, and_ # Add this line
)
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename
from pydantic import BaseModel, Field, constr, field_validator, validator # Ensure these are imported
import datetime # Ensure datetime is imported

from backend.database_setup import Personality as DBPersonality # Add this import at the top of main.py
from backend.config import *
# Local Application Imports
from backend.database_setup import (
    User as DBUser,
    UserStarredDiscussion,
    UserMessageGrade,
    FriendshipStatus,Friendship, 
    DataStore as DBDataStore,
    SharedDataStoreLink as DBSharedDataStoreLink,
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY,
)
from lollms_client import (
    LollmsClient,
    MSG_TYPE,
    LollmsDiscussion,
    DatabaseManager,
    ELF_COMPLETION_FORMAT, # For client params
)

# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import (
        LogLevel as SafeStoreLogLevel,
    )
except ImportError:
    print(
        "WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]"
    )
    safe_store = None
    SafeStoreLogLevel = None


from backend.message import AppLollmsMessage

class AppLollmsDiscussion:
    def __init__(
        self,
        lollms_client_instance: LollmsClient,
        db_manager: DatabaseManager,
        discussion_id: Optional[str] = None,
        title: Optional[str] = None,
    ):
        self.messages: List[AppLollmsMessage] = []
        self.lollms_client: LollmsClient = lollms_client_instance
        # RAG datastore to use for this discussion (can be set by user)
        self.lollms_discussion = LollmsDiscussion.create_new(
            lollms_client=self.lollms_client,
            db_manager=db_manager,
            autosave=True, # Recommended for interactive apps
            title = title,
            rag_datastore_ids=[]
        )
        


    def add_message(
        self,
        sender: str,
        sender_type: str,
        content: str,
        parent_message_id: Optional[str] = None,
        binding_name: Optional[str] = None,
        model_name: Optional[str] = None,
        token_count: Optional[int] = None,
        sources: Optional[List[Dict]] = None,
        steps: Optional[List[Dict]] = None,
        image_references: Optional[List[str]] = None,
    ) -> AppLollmsMessage:
        
        
        id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
        discussion_id = Column(String, ForeignKey('discussions.id'), nullable=False)
        parent_id = Column(String, ForeignKey('messages.id'), nullable=True)
        sender = Column(String, nullable=False)
        sender_type = Column(String, nullable=False)
        content = Column(EncryptedText, nullable=False)
        message_metadata = Column(JSON, nullable=True, default=dict)
        images = Column(JSON, nullable=True, default=list)
        created_at = Column(DateTime, default=datetime.utcnow)        
        
        message = self.lollms_discussion.add_message(
            sender=sender, 
            sender_type=sender_type,
            content=content, 
            parent_id=parent_message_id,
        )
        self.messages.append(message)
        return message

    def edit_message(self, message_id: str, new_content: str) -> bool:
        for msg in self.messages:
            if msg.id == message_id:
                msg.content = new_content
                if msg.sender.lower() != self.lollms_client.user_name.lower():
                    try: msg.token_count = self.lollms_client.binding.count_tokens(new_content)
                    except Exception: msg.token_count = len(new_content) // 3
                return True
        return False

    def delete_message(self, message_id: str) -> bool:
        original_len = len(self.messages)
        self.messages = [msg for msg in self.messages if msg.id != message_id]
        # TODO: Optionally delete associated image assets from disk
        return len(self.messages) < original_len

    # --- NEW METHOD TO ADD ---
    def get_message(self, message_id: str) -> Optional[AppLollmsMessage]:
        """Finds a message by its ID."""
        for msg in self.messages:
            if msg.id == message_id:
                return msg
        return None
    # --- END OF NEW METHOD ---

    def get_message_children(self, message_id: str) -> List[AppLollmsMessage]:
        """Finds all direct children of a given message."""
        children = [msg for msg in self.messages if msg.parent_message_id == message_id]
        # Sort by creation time to ensure consistent order
        return sorted(children, key=lambda m: m.created_at or datetime.datetime.min)

    def get_path_to_message(self, message_id: str) -> List[AppLollmsMessage]:
        """Traces the ancestry of a message back to the root of the discussion."""
        if message_id=="main":
            message_id = self.messages[-1].id
        messages_by_id = {msg.id: msg for msg in self.messages}
        if message_id not in messages_by_id:
            return []
        
        path = []
        current_msg_id = message_id
        while current_msg_id:
            msg = messages_by_id.get(current_msg_id)
            if not msg:
                break # Should not happen in a consistent tree
            path.append(msg)
            current_msg_id = msg.parent_message_id
        
        return path[::-1] # Reverse to get root -> leaf order

    def _generate_title_from_messages_if_needed(self) -> None:
        title = self.lollms_discussion.metadata.get("title", "New Discussion")
        is_generic_title = (
            title.startswith("New Discussion") or title.startswith("Imported") or
            title.startswith("Discussion ") or title.startswith("Sent: ") or not title.strip()
        )
        if is_generic_title and self.messages:
            first_user_message = next((m for m in self.messages if m.sender.lower() == self.lollms_client.user_name.lower()), None)
            if first_user_message:
                content_to_use = first_user_message.content
                if not content_to_use and first_user_message.image_references:
                    content_to_use = f"Image: {Path(first_user_message.image_references[0]).name}"

                if content_to_use:
                    new_title_base = content_to_use.strip().split("\n")[0]
                    max_title_len = 50
                    new_title = (new_title_base[: max_title_len - 3] + "...") if len(new_title_base) > max_title_len else new_title_base
                    if new_title: self.lollms_discussion.metadata["title"]= new_title
                    

    def to_dict(self) -> Dict[str, Any]:
        self._generate_title_from_messages_if_needed()
        return {
            "discussion_id": self.discussion_id,
            "title": self.lollms_discussion.get("title"),
            "messages": [message.to_dict() for message in self.messages],
            "rag_datastore_id": self.rag_datastore_id,
            "active_branch_id": self.active_branch_id # Persist active branch
        }

    def save_to_disk(self, file_path: Union[str, Path]) -> None:
        data_to_save = self.to_dict()
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            yaml.dump(data_to_save, file, sort_keys=False, allow_unicode=True, Dumper=yaml.SafeDumper)

    @classmethod
    def load_from_disk(
        cls, lollms_client_instance: LollmsClient, db_manager:DatabaseManager, file_path: Union[str, Path]
    ) -> Optional["AppLollmsDiscussion"]:
        actual_path = Path(file_path)
        if not actual_path.exists():
            print(f"WARNING: Discussion file not found: {actual_path}")
            return None
        try:
            with open(actual_path, "r", encoding="utf-8") as file: data = yaml.safe_load(file)
        except (yaml.YAMLError, IOError) as e:
            print(f"ERROR: Could not load/parse discussion from {actual_path}: {e}")
            return None

        if not isinstance(data, dict):
            print(f"WARNING: Old discussion format in {actual_path}. Attempting migration.")
            disc_id_from_path = actual_path.stem
            discussion = cls(lollms_client_instance, discussion_id=disc_id_from_path, title=f"Imported {disc_id_from_path[:8]}")
            if isinstance(data, list):
                for msg_data in data:
                    if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                        discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
            discussion._generate_title_from_messages_if_needed()
            return discussion

        discussion_id = data.get("discussion_id", actual_path.stem)
        title = data.get("title", f"Imported {discussion_id[:8]}")
        discussion = cls(lollms_client_instance, db_manager = db_manager, discussion_id=discussion_id, title=title)
        discussion.rag_datastore_id = data.get("rag_datastore_id")
        discussion.active_branch_id = data.get("active_branch_id") # Load active branch

        loaded_messages_data = data.get("messages", [])
        if isinstance(loaded_messages_data, list):
            for msg_data in loaded_messages_data:
                if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                    discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
                else:
                    print(f"WARNING: Skipping malformed message data in {actual_path}: {msg_data}")
        
        if (not discussion.lollms_discussion.metadata.get("title") or discussion.lollms_discussion.metadata.get("title").startswith("Imported ") or discussion.lollms_discussion.metadata.get("title").startswith("New Discussion ") or discussion.lollms_discussion.metadata.get("title").startswith("Sent: ")):
            discussion._generate_title_from_messages_if_needed()
        return discussion

    
    def get_branch_tip(self, start_message_id: str) -> str:
        """
        Finds the tip (leaf message) of a branch starting from a given message_id.
        It follows the path of single children. If multiple children are found, 
        it follows the first child by default to define a deterministic path.
        If the start_message_id is invalid, it returns the id itself.
        """
        if not self.get_message(start_message_id):
            # The provided ID doesn't exist in the discussion, can't find a tip.
            return start_message_id

        current_message_id = start_message_id
        while True:
            # get_message_children should be efficient (e.g., using a pre-built map)
            children = self.get_message_children(current_message_id)
            
            if not children:
                # No more children, this is a leaf node and therefore the tip of this branch.
                return current_message_id
            
            # By convention, follow the first child to trace the "main" path of this branch.
            # This ensures a predictable branch is returned when starting from a message
            # that may have multiple direct children.
            current_message_id = children[0].id
