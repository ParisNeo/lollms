
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
import io

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
    LollmsDiscussion as LollmsClientDiscussion,
    ELF_COMPLETION_FORMAT, # For client params
)

# --- Pydantic Models for API ---
from backend.models import (
UserLLMParams,
UserAuthDetails,
UserCreateAdmin,
UserPasswordResetAdmin,UserPasswordChange,
UserPublic,
DiscussionInfo,
DiscussionTitleUpdate,
DiscussionRagDatastoreUpdate,MessageOutput,
MessageContentUpdate,
MessageGradeUpdate,
SafeStoreDocumentInfo,
DiscussionExportRequest,
ExportData,
DiscussionImportRequest,
DiscussionSendRequest,
DataStoreBase,
DataStoreCreate,
DataStorePublic,
DataStoreShareRequest,
PersonalityBase,
PersonalityCreate,
PersonalityUpdate,
PersonalityPublic,
UserUpdate,
FriendshipBase,
FriendRequestCreate,
FriendshipAction,
FriendPublic,
FriendshipRequestPublic,
PersonalitySendRequest,

DirectMessagePublic,
DirectMessageCreate
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
        discussion_id: Optional[str] = None,
        title: Optional[str] = None,
    ):
        self.messages: List[AppLollmsMessage] = []
        self.lollms_client: LollmsClient = lollms_client_instance
        self.discussion_id: str = discussion_id or str(uuid.uuid4())
        raw_title = title or f"New Discussion {self.discussion_id[:8]}"
        self.title: str = (
            (raw_title[:250] + "...") if len(raw_title) > 253 else raw_title
        )
        # RAG datastore to use for this discussion (can be set by user)
        self.rag_datastore_id: Optional[str] = None


    def add_message(
        self,
        sender: str,
        content: str,
        parent_message_id: Optional[str] = None,
        binding_name: Optional[str] = None,
        model_name: Optional[str] = None,
        token_count: Optional[int] = None,
        image_references: Optional[List[str]] = None,
    ) -> AppLollmsMessage:
        message = AppLollmsMessage(
            sender=sender, content=content, parent_message_id=parent_message_id,
            binding_name=binding_name, model_name=model_name, token_count=token_count,
            image_references=image_references or []
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

    def _generate_title_from_messages_if_needed(self) -> None:
        is_generic_title = (
            self.title.startswith("New Discussion") or self.title.startswith("Imported") or
            self.title.startswith("Discussion ") or self.title.startswith("Sent: ") or not self.title.strip()
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
                    if new_title: self.title = new_title


    def to_dict(self) -> Dict[str, Any]:
        self._generate_title_from_messages_if_needed()
        return {
            "discussion_id": self.discussion_id,
            "title": self.title,
            "messages": [message.to_dict() for message in self.messages],
            "rag_datastore_id": self.rag_datastore_id, # Persist selected datastore
        }

    def save_to_disk(self, file_path: Union[str, Path]) -> None:
        data_to_save = self.to_dict()
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            yaml.dump(data_to_save, file, sort_keys=False, allow_unicode=True, Dumper=yaml.SafeDumper)

    @classmethod
    def load_from_disk(
        cls, lollms_client_instance: LollmsClient, file_path: Union[str, Path]
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
        discussion = cls(lollms_client_instance, discussion_id=discussion_id, title=title)
        discussion.rag_datastore_id = data.get("rag_datastore_id") # Load selected datastore

        loaded_messages_data = data.get("messages", [])
        if isinstance(loaded_messages_data, list):
            for msg_data in loaded_messages_data:
                if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                    discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
                else:
                    print(f"WARNING: Skipping malformed message data in {actual_path}: {msg_data}")
        
        if (not discussion.title or discussion.title.startswith("Imported ") or discussion.title.startswith("New Discussion ") or discussion.title.startswith("Sent: ")):
            discussion._generate_title_from_messages_if_needed()
        return discussion

    def prepare_query_for_llm(
        self, extra_content: str, 
        # image_paths_for_llm: Optional[List[str]], # This is handled by LollmsClient.generate_text directly
        max_total_tokens: Optional[int] = None
        # active_personality_system_prompt is no longer needed here
    ) -> str: # Returns only the user-facing part of the prompt including history
        lc = self.lollms_client
        
        if max_total_tokens is None:
            max_total_tokens = getattr(lc, "default_ctx_size", LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 32000))

        client_discussion = LollmsClientDiscussion(lc)
        for app_msg in self.messages:
            client_discussion.add_message(sender=app_msg.sender, content=app_msg.content)

        user_prefix = f"{lc.user_full_header}"
        ai_prefix = f"{lc.ai_full_header}"
        
        # The prompt passed to LollmsClient.generate_text will be the current user turn.
        # The history will be managed by LollmsClient itself if we pass the discussion object,
        # or we format it here and pass it as part of the prompt.
        # Let's assume LollmsClient.generate_text can take the full prompt (history + current turn)
        # and a separate system_prompt.

        # Calculate tokens for the current turn's text to determine history budget
        # The system_prompt tokens will be handled separately by the caller of generate_text
        current_turn_formatted_text_only = f"{user_prefix}\n{extra_content}\n{ai_prefix}"
        try:
            current_turn_tokens = self.lollms_client.binding.count_tokens(current_turn_formatted_text_only)
        except Exception:
            current_turn_tokens = len(current_turn_formatted_text_only) // 3 # Fallback

        # The max_total_tokens should account for the system_prompt, which will be passed separately.
        # So, the history + current_prompt should fit within (max_total_tokens - system_prompt_tokens).
        # Since this function doesn't know the system_prompt_tokens, the caller of generate_text
        # needs to be mindful or LollmsClient needs to handle truncation considering all parts.

        # For simplicity here, let's assume max_total_tokens is for history + current_prompt.
        # The LollmsClient will then internally manage this with its own context size and the provided system_prompt.
        tokens_for_history = max_total_tokens - current_turn_tokens
        if tokens_for_history < 0: tokens_for_history = 0
        
        history_text = client_discussion.format_discussion(max_allowed_tokens=tokens_for_history)
        
        # The prompt to return is the history + current user turn, ready for the AI.
        # The system prompt will be passed as a separate argument to generate_text.
        full_user_facing_prompt = f"{extra_content}{history_text}\n{ai_prefix}"
        
        return full_user_facing_prompt

