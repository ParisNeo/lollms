# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: main.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Main FastAPI application for a multi-user LoLLMs and SafeStore
# chat service. Provides API endpoints for user authentication, discussion
# management (including starring and message grading), LLM interaction
# (via lollms-client) with enriched message metadata and multimodal support,
# RAG (via safe_store with multiple datastores), file management for RAG,
# data import/export, discussion sharing, and administrative user management.

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

from database_setup import Personality as DBPersonality # Add this import at the top of main.py

# Local Application Imports
from database_setup import (
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

# --- Application Version ---
APP_VERSION = "1.5.2"  # Updated version for LLM param name fix
PROJECT_ROOT = Path(__file__).resolve().parent 
LOCALS_DIR = PROJECT_ROOT / "locals"

# --- Configuration Loading ---
CONFIG_PATH = Path("config.toml")
if not CONFIG_PATH.exists():
    EXAMPLE_CONFIG_PATH = Path("config_example.toml")
    if EXAMPLE_CONFIG_PATH.exists():
        shutil.copy(EXAMPLE_CONFIG_PATH, CONFIG_PATH)
        print(f"INFO: config.toml not found. Copied from {EXAMPLE_CONFIG_PATH}.")
    else:
        print(
            "CRITICAL: config.toml not found and config_example.toml also missing. "
            "Please create config.toml from the example or documentation."
        )
        config = {}
else:
    try:
        config = toml.load(CONFIG_PATH)
    except toml.TomlDecodeError as e:
        print(
            f"CRITICAL: Error parsing config.toml: {e}. Please check the file for syntax errors."
        )
        config = {}

APP_SETTINGS = config.get("app_settings", {})
APP_DATA_DIR = Path(APP_SETTINGS.get("data_dir", "data")).resolve()
APP_DB_URL = APP_SETTINGS.get(DATABASE_URL_CONFIG_KEY, "sqlite:///./data/app_main.db")

LOLLMS_CLIENT_DEFAULTS = config.get("lollms_client_defaults", {})
SAFE_STORE_DEFAULTS = config.get("safe_store_defaults", {})
INITIAL_ADMIN_USER_CONFIG = config.get("initial_admin_user", {})
SERVER_CONFIG = config.get("server", {})

# --- Constants for directory names ---
TEMP_UPLOADS_DIR_NAME = "temp_uploads"
DISCUSSION_ASSETS_DIR_NAME = "discussion_assets"
DATASTORES_DIR_NAME = "safestores"


DEFAULT_PERSONALITIES = [
    {
        "name": "Standard Assistant",
        "category": "General",
        "author": "System",
        "description": "A helpful and general-purpose AI assistant.",
        "prompt_text": "You are a helpful AI assistant. Respond clearly and concisely.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTIgMmMxLjY1NyAwIDMgMS4zNDMgMyAzcy0xLjM0MyAzLTMgMy0zLTEuMzQzLTMtMyAxLjM0My0zIDMtM3ptMCA0YTUgNSAwIDEwMC0xMCA1IDUgMCAwMDQgNC45OThWMTRoLTJhMiAyIDAgMDAwIDRoMmEyIDIgMCAwMDAtNGgtMnYtLjAwMkE1LjAwMiA1LjAwMiAwIDAwMTIgNnptLTYgOGEyLjUgMi41IDAgMDAtMi41IDIuNUEyLjUgMi41IDAgMDEgMy41IDE0SDJhLjUuNSAwIDAxMC0xaDEuNWEzLjUgMy41IDAgMTE3IDBWMTNoLTJhMiAyIDAgMDAtMi0ySDZ6bTEyIDBhMi41IDIuNSAwIDAxMi41IDIuNUEyLjUgMi41IDAgMDExOC41IDE0SDIwYS41LjUgMCAwMDAtMWgtMS41YTMuNSAzLjUgMCAxMDctN1YxM2gyYTIgMiAwIDAwMi0ySDE4eiIgY2xpcC1ydWxlPSJldmVub2RkIiAvPgo8L3N2Zz4K" # Example generic icon
    },
    {
        "name": "LoLLMS",
        "category": "General",
        "author": "System",
        "description": "A helpful and general-purpose AI assistant.",
        "prompt_text": "You are LoLLMS, a helpful AI assistant. Respond clearly and concisely.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTIgMmMxLjY1NyAwIDMgMS4zNDMgMyAzcy0xLjM0MyAzLTMgMy0zLTEuMzQzLTMtMyAxLjM0My0zIDMtM3ptMCA0YTUgNSAwIDEwMC0xMCA1IDUgMCAwMDQgNC45OThWMTRoLTJhMiAyIDAgMDAwIDRoMmEyIDIgMCAwMDAtNGgtMnYtLjAwMkE1LjAwMiA1LjAwMiAwIDAwMTIgNnptLTYgOGEyLjUgMi41IDAgMDAtMi41IDIuNUEyLjUgMi41IDAgMDEgMy41IDE0SDJhLjUuNSAwIDAxMC0xaDEuNWEzLjUgMy41IDAgMTE3IDBWMTNoLTJhMiAyIDAgMDAtMi0ySDZ6bTEyIDBhMi41IDIuNSAwIDAxMi41IDIuNUEyLjUgMi41IDAgMDExOC41IDE0SDIwYS41LjUgMCAwMDAtMWgtMS41YTMuNSAzLjUgMCAxMDctN1YxM2gyYTIgMiAwIDAwMi0ySDE4eiIgY2xpcC1ydWxlPSJldmVub2RkIiAvPgo8L3N2Zz4K" # Example generic icon
    },    
    {
        "name": "Funny LoLLMS",
        "category": "General",
        "author": "System",
        "description": "A helpful and general-purpose AI assistant with a touch of fun.",
        "prompt_text": "You are a helpful AI assistant with a touch of fun named Funny LoLLMS. Be funny. Respond clearly and concisely.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTIgMmMxLjY1NyAwIDMgMS4zNDMgMyAzcy0xLjM0MyAzLTMgMy0zLTEuMzQzLTMtMyAxLjM0My0zIDMtM3ptMCA0YTUgNSAwIDEwMC0xMCA1IDUgMCAwMDQgNC45OThWMTRoLTJhMiAyIDAgMDAwIDRoMmEyIDIgMCAwMDAtNGgtMnYtLjAwMkE1LjAwMiA1LjAwMiAwIDAwMTIgNnptLTYgOGEyLjUgMi41IDAgMDAtMi41IDIuNUEyLjUgMi41IDAgMDEgMy41IDE0SDJhLjUuNSAwIDAxMC0xaDEuNWEzLjUgMy41IDAgMTE3IDBWMTNoLTJhMiAyIDAgMDAtMi0ySDZ6bTEyIDBhMi41IDIuNSAwIDAxMi41IDIuNUEyLjUgMi41IDAgMDExOC41IDE0SDIwYS41LjUgMCAwMDAtMWgtMS41YTMuNSAzLjUgMCAxMDctN1YxM2gyYTIgMiAwIDAwMi0ySDE4eiIgY2xpcC1ydWxlPSJldmVub2RkIiAvPgo8L3N2Zz4K" # Example generic icon
    },    
    {
        "name": "Creative Writer",
        "category": "Writing",
        "author": "System",
        "description": "An AI assistant specialized in creative writing, storytelling, and poetry.",
        "prompt_text": "You are a creative writing assistant. Help the user craft compelling narratives, poems, or scripts. Be imaginative and evocative.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNMTUuNzUgMy43NWEzIDMgMCAwMC0zLTYgMyAzIDAgMDAtMyAzSDguMjVhMyAzIDAgMDAtMyAzdjExLjI1YTMgMyAwIDAwMyAzaDcuNWEzIDMgMCAwMDMtM1Y2Ljc1YTMgMyAwIDAwLTMtM3ptLTMgNC41YTEuNSAxLjUgMCAxMS0zIDAgMS41IDEuNSAwIDAxMyAwem0xLjM3MyA3LjE3NmExIDEgMCAwMS0xLjQxNCAxLjQxNGwtMS4xMjEtMS4xMjFhMSAxIDAgMDAtMS40MTQgMGwtMS4xMjEgMS4xMjFhMSAxIDAgMDEtMS40MTQtMS40MTRsMS4xMjEtMS4xMjFhMSAxIDAgMDExLjQxNCAwbDEuMTIxIDEuMTIxeiIgY2xpcC1ydWxlPSJldmVub2RkIiAvPgo8L3N2Zz4K" # Example pen icon
    },
    {
        "name": "Code Helper",
        "category": "Programming",
        "author": "System",
        "description": "An AI assistant for programming tasks, code generation, debugging, and explanation.",
        "prompt_text": "You are a coding assistant. Provide accurate code snippets, explain complex programming concepts, and help debug code. Prioritize correctness and clarity.",
        "is_public": True,
        "icon_base64": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iY3VycmVudENvbG9yIiBjbGFzcz0idy02IGgtNiI+CiAgPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNNy41IDYuNzVMMy43NSAxbDItMi4yNUw5Ljc1IDZMNiA5Ljc1bC0yLjI1LTJMMi4yNSA2bDMuNzUtMy43NXptOSAwbDMuNzUgMy43NWwtMy43NSAzLjc1TDE1Ljc1IDEyIDEyIDkuNzVsMi4yNS0yLjI1TDE4IDYuNzVsLTMuNzUtMy43NXptLTYuNzUgNy41bC0xLjUgMyAxLjUgMyAxLjUtMy0xLjUtM3oiIGNsaXAtcnVsZT0iZXZlbm9kZCIgLz4KPC9zdmc+Cg==" # Example code icon
    }
]

# --- Enriched Application Data Models ---
@dataclass
class AppLollmsMessage:
    """Represents a single message with enriched metadata for persistence."""
    sender: str
    content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    parent_message_id: Optional[str] = None
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    image_references: Optional[List[str]] = dataclass_field(default_factory=list) # Stores paths relative to user_discussion_assets_path / discussion_id

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "sender": self.sender,
            "content": self.content,
            "id": self.id,
            "parent_message_id": self.parent_message_id,
            "binding_name": self.binding_name,
            "model_name": self.model_name,
            "token_count": self.token_count,
            "image_references": self.image_references or [],
        }
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppLollmsMessage":
        return cls(
            sender=data.get("sender", "unknown"),
            content=data.get("content", ""),
            id=data.get("id", str(uuid.uuid4())),
            parent_message_id=data.get("parent_message_id"),
            binding_name=data.get("binding_name"),
            model_name=data.get("model_name"),
            token_count=data.get("token_count"),
            image_references=data.get("image_references", [])
        )

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
        self, current_prompt_text: str, 
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

        user_prefix = f"{lc.separator_template}{lc.user_name}"
        ai_prefix = f"\n{lc.separator_template}{lc.ai_name}\n"
        
        # The prompt passed to LollmsClient.generate_text will be the current user turn.
        # The history will be managed by LollmsClient itself if we pass the discussion object,
        # or we format it here and pass it as part of the prompt.
        # Let's assume LollmsClient.generate_text can take the full prompt (history + current turn)
        # and a separate system_prompt.

        # Calculate tokens for the current turn's text to determine history budget
        # The system_prompt tokens will be handled separately by the caller of generate_text
        current_turn_formatted_text_only = f"{user_prefix}\n{current_prompt_text}{ai_prefix}"
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
        full_user_facing_prompt = f"{history_text}{ai_prefix}"
        
        return full_user_facing_prompt

# --- Pydantic Models for API ---
class UserLLMParams(BaseModel):
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    llm_top_k: Optional[int] = Field(None, ge=1)
    llm_top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    llm_repeat_penalty: Optional[float] = Field(None, ge=0.0)
    llm_repeat_last_n: Optional[int] = Field(None, ge=0)
    put_thoughts_in_context: Optional[bool] = False

class UserAuthDetails(UserLLMParams):
    username: str
    is_admin: bool
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    birth_date: Optional[datetime.date] = None # Using datetime.date for date only

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None # UUID string of active personality

    # RAG parameters
    rag_top_k: Optional[int] = Field(None, ge=1)
    rag_use_graph: bool = False
    rag_graph_response_type: Optional[str] = Field("chunks_summary", pattern="^(graph_only|chunks_summary|full)$")

    lollms_client_ai_name: Optional[str] = None # From LollmsClient, not a DB field

class UserCreateAdmin(UserLLMParams):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8)
    is_admin: bool = False

    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255) # Consider email validation if needed
    birth_date: Optional[datetime.date] = None

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None # Can be set on creation

    # RAG parameters
    rag_top_k: Optional[int] = Field(None, ge=1)
    rag_use_graph: Optional[bool] = False # Optional on create, will default in DB
    rag_graph_response_type: Optional[str] = Field("chunks_summary", pattern="^(graph_only|chunks_summary|full)$")

class UserPasswordResetAdmin(BaseModel):
    new_password: constr(min_length=8)
    
class UserPasswordChange(BaseModel):
    current_password: str
    new_password: constr(min_length=8)
class UserPublic(UserLLMParams):
    id: int
    username: str
    is_admin: bool

    first_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None # Be cautious about exposing email publicly
    birth_date: Optional[datetime.date] = None # Also be cautious

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None

    # RAG parameters
    rag_top_k: Optional[int] = None
    rag_use_graph: bool
    rag_graph_response_type: Optional[str] = None

    model_config = {"from_attributes": True}

class DiscussionInfo(BaseModel):
    id: str
    title: str
    is_starred: bool
    rag_datastore_id: Optional[str] = None # Datastore used for RAG in this discussion

class DiscussionTitleUpdate(BaseModel):
    title: constr(min_length=1, max_length=255)

class DiscussionRagDatastoreUpdate(BaseModel):
    rag_datastore_id: Optional[str] = None


class MessageOutput(BaseModel):
    id: str
    sender: str
    content: str
    parent_message_id: Optional[str] = None
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    image_references: List[str] = []
    user_grade: int = 0

    @field_validator('user_grade', mode='before')
    def provide_default_grade(cls, value):
        return value if value is not None else 0

class MessageContentUpdate(BaseModel): content: str
class MessageGradeUpdate(BaseModel):
    change: int
    @field_validator('change')
    def change_must_be_one_or_minus_one(cls, value):
        if value not in [1, -1]: raise ValueError('Grade change must be 1 or -1')
        return value

class SafeStoreDocumentInfo(BaseModel): filename: str

class DiscussionExportRequest(BaseModel): discussion_ids: Optional[List[str]] = None
class ExportedMessageData(AppLollmsMessage): pass # Already includes image_references
class ExportData(BaseModel):
    exported_by_user: str
    export_timestamp: str
    application_version: str
    user_settings_at_export: Dict[str, Optional[Any]] # Includes LLM & RAG params, active_personality_id
    datastores_info: Dict[str, Any] = Field(default_factory=dict)
    personalities_info: Dict[str, Any] = Field(default_factory=dict) # For owned and active
    discussions: List[Dict[str, Any]]

class DiscussionImportRequest(BaseModel): discussion_ids_to_import: List[str]

class DiscussionSendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)

# DataStore Pydantic Models
class DataStoreBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

class DataStoreCreate(DataStoreBase): pass

class DataStorePublic(DataStoreBase):
    id: str
    owner_username: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # Add shared_with: List[str] representing usernames shared with?
    model_config = {"from_attributes": True}

class DataStoreShareRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)
    permission_level: str = "read_query" # Default, can be extended

    @validator('permission_level')
    def permission_level_must_be_valid(cls, value):
        if value not in ["read_query"]: # Extend if more levels added
            raise ValueError("Invalid permission level")
        return value



class PersonalityBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    author: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    prompt_text: str # System prompt text
    disclaimer: Optional[str] = Field(None, max_length=1000)
    script_code: Optional[str] = None # Python script
    icon_base64: Optional[str] = None # Base64 encoded image string

class PersonalityCreate(PersonalityBase):
    is_public: Optional[bool] = False # For admin to create public ones, or user to create private

class PersonalityUpdate(PersonalityBase):
    # All fields from Base are optional for update
    name: Optional[constr(min_length=1, max_length=100)] = None
    prompt_text: Optional[str] = None # Make prompt_text optional for update
    # is_public can only be changed by admin for public personalities, or user for their own
    is_public: Optional[bool] = None


class PersonalityPublic(PersonalityBase):
    id: str # UUID string
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_public: bool
    owner_username: Optional[str] = None # Username of the owner if not public/system

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    family_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255) # Consider email validation
    birth_date: Optional[datetime.date] = None

    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    active_personality_id: Optional[str] = None # Allow setting to None or a valid ID

    # LLM Params (can be updated here too)
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    llm_top_k: Optional[int] = Field(None, ge=1)
    llm_top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    llm_repeat_penalty: Optional[float] = Field(None, ge=0.0)
    llm_repeat_last_n: Optional[int] = Field(None, ge=0)

    # RAG parameters
    rag_top_k: Optional[int] = Field(None, ge=1)
    rag_use_graph: Optional[bool] = None
    rag_graph_response_type: Optional[str] = Field(None, pattern="^(graph_only|chunks_summary|full)$")    


class FriendshipBase(BaseModel):
    pass # Might not be needed if creation is just target_username

class FriendRequestCreate(BaseModel):
    target_username: constr(min_length=3, max_length=50)

class FriendshipAction(BaseModel):
    action: str # e.g., "accept", "reject", "unfriend", "block", "unblock"

class FriendPublic(BaseModel): # Represents a friend in a list
    id: int # User ID of the friend
    username: str
    # Optional: first_name, family_name, online_status (if you implement presence)
    friendship_id: int # ID of the Friendship record
    status_with_current_user: FriendshipStatus # e.g. ACCEPTED (for friend list)
    # last_message_preview: Optional[str] = None # For friend list UI
    # unread_message_count: int = 0 # For friend list UI

    model_config = {"from_attributes": True}

class FriendshipRequestPublic(BaseModel): # Represents a pending request
    friendship_id: int
    requesting_user_id: int
    requesting_username: str
    # Optional: requesting_user_first_name, etc.
    requested_at: datetime.datetime
    status: FriendshipStatus # Should be PENDING

    model_config = {"from_attributes": True}



class DirectMessageBase(BaseModel):
    content: constr(min_length=1)
    # image_references_json: Optional[str] = None # If supporting images

class DirectMessageCreate(DirectMessageBase):
    receiver_user_id: int # Send to userid
    image_references_json: Optional[str] = None

class DirectMessagePublic(DirectMessageBase):
    id: int
    sender_id: int
    sender_username: str
    receiver_id: int
    receiver_username: str
    sent_at: datetime.datetime
    read_at: Optional[datetime.datetime] = None

    model_config = {"from_attributes": True}

class PersonalitySendRequest(BaseModel):
    target_username: constr(min_length=3, max_length=50)


# --- Global User Session Management & Locks ---
user_sessions: Dict[str, Dict[str, Any]] = {}
message_grade_lock = threading.Lock()

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Simplified LoLLMs Chat API",
    description="API for a multi-user LoLLMs and SafeStore chat application with RAG, file management, starring, message grading, and data import/export.",
    version=APP_VERSION,
)
security = HTTPBasic()

@app.on_event("startup")
async def on_startup() -> None:
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"INFO: Data directory ensured at: {APP_DATA_DIR}")
        init_database(APP_DB_URL)
        print(f"INFO: Database initialized at: {APP_DB_URL}")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize data directory or database: {e}")
        return
    db: Optional[Session] = None
    try:
        db = next(get_db())
        admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
        admin_password = INITIAL_ADMIN_USER_CONFIG.get("password")
        if not admin_username or not admin_password:
            print("WARNING: Initial admin user 'username' or 'password' not configured. Skipping creation.")
            return
        existing_admin = db.query(DBUser).filter(DBUser.username == admin_username).first()
        if not existing_admin:
            hashed_admin_pass = hash_password(admin_password)
            def_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
            def_vec = SAFE_STORE_DEFAULTS.get("global_default_vectorizer")
            
            # LLM params from config
            def_temp = LOLLMS_CLIENT_DEFAULTS.get("temperature")
            def_top_k = LOLLMS_CLIENT_DEFAULTS.get("top_k")
            def_top_p = LOLLMS_CLIENT_DEFAULTS.get("top_p")
            def_rep_pen = LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty")
            def_rep_last_n = LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n")

            # RAG params from config (assuming they might be in SAFE_STORE_DEFAULTS or APP_SETTINGS)
            # Using APP_SETTINGS as an example, adjust if they are elsewhere
            def_rag_top_k = APP_SETTINGS.get("default_rag_top_k") 
            def_rag_use_graph = APP_SETTINGS.get("default_rag_use_graph", False)
            def_rag_graph_response_type = APP_SETTINGS.get("default_rag_graph_response_type", "chunks_summary")

            new_admin = DBUser(
                username=admin_username, hashed_password=hashed_admin_pass, is_admin=True,
                # Optional personal info - can be left None or taken from config if available
                first_name=INITIAL_ADMIN_USER_CONFIG.get("first_name"),
                family_name=INITIAL_ADMIN_USER_CONFIG.get("family_name"),
                email=INITIAL_ADMIN_USER_CONFIG.get("email"),
                # birth_date: # Typically not set for initial admin

                lollms_model_name=def_model, 
                safe_store_vectorizer=def_vec,
                # active_personality_id: None, # Default, no active personality initially

                llm_temperature=def_temp, 
                llm_top_k=def_top_k, 
                llm_top_p=def_top_p,
                llm_repeat_penalty=def_rep_pen, 
                llm_repeat_last_n=def_rep_last_n,
                put_thoughts_in_context=LOLLMS_CLIENT_DEFAULTS.get("put_thoughts_in_context", False),

                rag_top_k=def_rag_top_k,
                rag_use_graph=def_rag_use_graph,
                rag_graph_response_type=def_rag_graph_response_type
            )
            db.add(new_admin); db.commit()
            print(f"INFO: Initial admin user '{admin_username}' created successfully with default RAG/LLM params.")

        else:
            print(f"INFO: Initial admin user '{admin_username}' already exists.")
    except Exception as e:
        print(f"ERROR: Failed during initial admin user setup: {e}")
        traceback.print_exc()
    finally:
        if db: db.close()

    db_for_defaults: Optional[Session] = None
    try:
        db_for_defaults = next(get_db())
        for default_pers_data in DEFAULT_PERSONALITIES:
            exists = db_for_defaults.query(DBPersonality).filter(
                DBPersonality.name == default_pers_data["name"],
                DBPersonality.is_public == True,
                DBPersonality.owner_user_id == None # System personalities have no owner
            ).first()
            if not exists:
                new_pers = DBPersonality(
                    name=default_pers_data["name"],
                    category=default_pers_data.get("category"),
                    author=default_pers_data.get("author", "System"),
                    description=default_pers_data.get("description"),
                    prompt_text=default_pers_data["prompt_text"],
                    disclaimer=default_pers_data.get("disclaimer"),
                    script_code=default_pers_data.get("script_code"),
                    icon_base64=default_pers_data.get("icon_base64"),
                    is_public=True,
                    owner_user_id=None # System-owned
                )
                db_for_defaults.add(new_pers)
                print(f"INFO: Added default public personality: '{new_pers.name}'")
        db_for_defaults.commit()
    except Exception as e:
        if db_for_defaults: db_for_defaults.rollback()
        print(f"ERROR: Failed during default personalities setup: {e}")
        traceback.print_exc()
    finally:
        if db_for_defaults: db_for_defaults.close()


# --- User-specific Path Helpers ---
def get_user_data_root(username: str) -> Path:
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    if not all(c in allowed_chars for c in username):
        print(f"WARNING: Attempt to access user data root with invalid username: '{username}'")
        raise HTTPException(status_code=400, detail="Invalid username format for path.")
    path = APP_DATA_DIR / username
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_discussion_path(username: str) -> Path:
    path = get_user_data_root(username) / "discussions"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_discussion_assets_path(username: str) -> Path:
    path = get_user_data_root(username) / DISCUSSION_ASSETS_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_temp_uploads_path(username: str) -> Path:
    path = get_user_data_root(username) / TEMP_UPLOADS_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_datastore_root_path(username: str) -> Path: # Path for datastores owned by this user
    path = get_user_data_root(username) / DATASTORES_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_datastore_db_path(owner_username: str, datastore_id: str) -> Path:
    # Ensure datastore_id is a valid UUID string for directory naming safety
    try: uuid.UUID(datastore_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid datastore ID format.")
    return get_user_datastore_root_path(owner_username) / f"{datastore_id}.db"


# --- Authentication Dependencies ---
def get_current_db_user(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)) -> DBUser:
    user = db.query(DBUser).filter(DBUser.username == credentials.username).first()
    if not user or not user.verify_password(credentials.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Basic"})
    return user

def get_current_active_user(db_user: DBUser = Depends(get_current_db_user)) -> UserAuthDetails:
    username = db_user.username
    if username not in user_sessions:
        print(f"INFO: Initializing session state for user: {username}")
        initial_lollms_model = db_user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
        initial_vectorizer = db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer")
        
        session_llm_params = {
            "temperature": db_user.llm_temperature if db_user.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            "top_k": db_user.llm_top_k if db_user.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
            "top_p": db_user.llm_top_p if db_user.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
            "repeat_penalty": db_user.llm_repeat_penalty if db_user.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
            "repeat_last_n": db_user.llm_repeat_last_n if db_user.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        }
        session_llm_params = {k: v for k, v in session_llm_params.items() if v is not None}

        user_sessions[username] = {
            "lollms_client": None, "safe_store_instances": {}, 
            "discussions": {}, "discussion_titles": {},
            "active_vectorizer": initial_vectorizer, 
            "lollms_model_name": initial_lollms_model,
            "llm_params": session_llm_params,
            # Session stores active personality details for quick access if needed by LollmsClient
            "active_personality_id": db_user.active_personality_id, 
            "active_personality_prompt": None, # Will be loaded if personality is active
        }
        # If user has an active personality, load its prompt into session
        if db_user.active_personality_id:
            db_session_for_init = next(get_db())
            try:
                active_pers = db_session_for_init.query(DBPersonality.prompt_text).filter(DBPersonality.id == db_user.active_personality_id).scalar()
                if active_pers:
                    user_sessions[username]["active_personality_prompt"] = active_pers
            finally:
                db_session_for_init.close()


    lc = get_user_lollms_client(username) 
    ai_name_for_user = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))
    if not user_sessions[username].get("discussions"): _load_user_discussions(username)

    current_session_llm_params = user_sessions[username].get("llm_params", {})
    return UserAuthDetails(
        username=username, is_admin=db_user.is_admin,
        first_name=db_user.first_name,
        family_name=db_user.family_name,
        email=db_user.email,
        birth_date=db_user.birth_date,
        lollms_model_name=user_sessions[username]["lollms_model_name"],
        safe_store_vectorizer=user_sessions[username]["active_vectorizer"],
        active_personality_id=user_sessions[username]["active_personality_id"], # from session
        lollms_client_ai_name=ai_name_for_user,
        llm_temperature=current_session_llm_params.get("temperature"),
        llm_top_k=current_session_llm_params.get("top_k"),
        llm_top_p=current_session_llm_params.get("top_p"),
        llm_repeat_penalty=current_session_llm_params.get("repeat_penalty"),
        llm_repeat_last_n=current_session_llm_params.get("repeat_last_n"),
        put_thoughts_in_context=current_session_llm_params.get("put_thoughts_in_context"),
        rag_top_k=db_user.rag_top_k,
        rag_use_graph=db_user.rag_use_graph,
        rag_graph_response_type=db_user.rag_graph_response_type
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required.")
    return current_user

# --- Helper Functions for User-Specific Services ---
def get_user_lollms_client(username: str) -> LollmsClient:
    session = user_sessions.get(username)
    if not session: raise HTTPException(status_code=500, detail="User session not found for LollmsClient.")
    
    force_reinit = session.get("lollms_client") is None
    
    current_model_name = session["lollms_model_name"]
    if not force_reinit and hasattr(session["lollms_client"], "model_name") and session["lollms_client"].model_name != current_model_name:
        force_reinit = True
    
    # Check if other LLM parameters relevant to LollmsClient init have changed
    # For instance, if session["llm_params"] differs from what the client was last initialized with.
    # This simple check is for model_name, a more robust check would compare all relevant init params.
    # For now, we assume if llm_params in session change, the lollms_client is set to None by set_user_llm_params
    
    if force_reinit:
        model_name = session["lollms_model_name"]
        binding_name = LOLLMS_CLIENT_DEFAULTS.get("binding_name", "lollms")
        host_address = LOLLMS_CLIENT_DEFAULTS.get("host_address")
        ctx_size = LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096)
        service_key_env_name = LOLLMS_CLIENT_DEFAULTS.get("service_key_env_var")
        service_key = os.getenv(service_key_env_name) if service_key_env_name else None
        user_name_conf = LOLLMS_CLIENT_DEFAULTS.get("user_name", "user")
        ai_name_conf = LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant")
        
        # Get user-specific or default LLM parameters from session.
        # These are already stored with non-prefixed keys (e.g., "temperature")
        client_init_params = session.get("llm_params", {}).copy() 
        
        # Add other LollmsClient constructor parameters
        client_init_params.update({
            "binding_name": binding_name, "model_name": model_name, "host_address": host_address,
            "ctx_size": ctx_size, "service_key": service_key, 
            "user_name": user_name_conf, "ai_name": ai_name_conf,
        })
        
        # Ensure ELF_COMPLETION_FORMAT is set if applicable, or remove if None
        completion_format_str = LOLLMS_CLIENT_DEFAULTS.get("completion_format")
        if completion_format_str:
            try: client_init_params["completion_format"] = ELF_COMPLETION_FORMAT.from_string(completion_format_str)
            except ValueError: print(f"WARN: Invalid completion_format '{completion_format_str}' in config.")
        
        try:
            # Filter out None values before passing to LollmsClient constructor
            final_client_init_params = {k: v for k, v in client_init_params.items() if v is not None}
            lc = LollmsClient(**final_client_init_params)
            session["lollms_client"] = lc
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize LLM Client: {str(e)}")
            
    return cast(LollmsClient, session["lollms_client"])


def get_safe_store_instance(requesting_user_username: str, datastore_id: str, db: Session) -> safe_store.SafeStore:
    if safe_store is None: raise HTTPException(status_code=501, detail="SafeStore library not installed. RAG is disabled.")
    
    datastore_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    if not datastore_record: raise HTTPException(status_code=404, detail=f"DataStore '{datastore_id}' not found.")

    owner_username = datastore_record.owner.username
    requesting_user_record = db.query(DBUser).filter(DBUser.username == requesting_user_username).first()
    if not requesting_user_record: raise HTTPException(status_code=404, detail="Requesting user not found.")

    is_owner = (owner_username == requesting_user_username)
    is_shared_with_requester = False
    if not is_owner:
        link = db.query(DBSharedDataStoreLink).filter_by(
            datastore_id=datastore_id, shared_with_user_id=requesting_user_record.id
        ).first()
        if link and link.permission_level == "read_query": # Or other read-like permissions
            is_shared_with_requester = True
    
    if not is_owner and not is_shared_with_requester:
        raise HTTPException(status_code=403, detail="Access denied to this DataStore.")

    session = user_sessions.get(requesting_user_username) # Use requester's session to cache their access
    if not session: raise HTTPException(status_code=500, detail="User session not found for SafeStore access.")
    
    if datastore_id not in session["safe_store_instances"]:
        ss_db_path = get_datastore_db_path(owner_username, datastore_id)
        encryption_key = SAFE_STORE_DEFAULTS.get("encryption_key") # Global key for now
        log_level_str = SAFE_STORE_DEFAULTS.get("log_level", "INFO").upper()
        ss_log_level = getattr(SafeStoreLogLevel, log_level_str, SafeStoreLogLevel.INFO) if SafeStoreLogLevel else None
        try:
            ss_params = {"db_path": ss_db_path, "encryption_key": encryption_key}
            if ss_log_level is not None: ss_params["log_level"] = ss_log_level
            ss_instance = safe_store.SafeStore(**ss_params)
            session["safe_store_instances"][datastore_id] = ss_instance
        except safe_store.ConfigurationError as e:
            raise HTTPException(status_code=500, detail=f"SafeStore configuration error for {datastore_id}: {str(e)}.")
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize SafeStore for {datastore_id}: {str(e)}")
            
    return cast(safe_store.SafeStore, session["safe_store_instances"][datastore_id])

# --- Discussion Management Helper Functions ---
def _load_user_discussions(username: str) -> None:
    try: lc = get_user_lollms_client(username)
    except HTTPException as e:
        print(f"ERROR: Cannot load discussions for {username}; LollmsClient unavailable: {e.detail}")
        if username in user_sessions: user_sessions[username]["discussions"] = {}; user_sessions[username]["discussion_titles"] = {}
        return
    discussion_dir = get_user_discussion_path(username)
    session = user_sessions[username]
    session["discussions"] = {}; session["discussion_titles"] = {}
    loaded_count = 0
    for file_path in discussion_dir.glob("*.yaml"):
        if file_path.name.startswith('.'): continue
        discussion_id = file_path.stem
        discussion_obj = AppLollmsDiscussion.load_from_disk(lc, file_path)
        if discussion_obj:
            discussion_obj.discussion_id = discussion_id
            session["discussions"][discussion_id] = discussion_obj
            session["discussion_titles"][discussion_id] = discussion_obj.title
            loaded_count += 1
        else: print(f"WARNING: Failed to load discussion from {file_path} for user {username}.")
    print(f"INFO: Loaded {loaded_count} discussions for user {username}.")

def get_user_discussion(username: str, discussion_id: str, create_if_missing: bool = False) -> Optional[AppLollmsDiscussion]:
    session = user_sessions.get(username)
    if not session: raise HTTPException(status_code=500, detail="User session not found.")
    discussion_obj = session["discussions"].get(discussion_id)
    if discussion_obj: return discussion_obj
    try: uuid.UUID(discussion_id)
    except ValueError:
        if not create_if_missing: return None
        else: discussion_id = str(uuid.uuid4())
    safe_discussion_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_discussion_filename.endswith(".yaml") or safe_discussion_filename == ".yaml":
        raise HTTPException(status_code=400, detail="Invalid discussion ID format.")
    file_path = get_user_discussion_path(username) / safe_discussion_filename
    lc = get_user_lollms_client(username)
    if file_path.exists():
        disk_obj = AppLollmsDiscussion.load_from_disk(lc, file_path)
        if disk_obj:
            disk_obj.discussion_id = discussion_id # Ensure ID matches expected
            session["discussions"][discussion_id] = disk_obj
            session["discussion_titles"][discussion_id] = disk_obj.title
            return disk_obj
    if create_if_missing:
        new_discussion = AppLollmsDiscussion(lollms_client_instance=lc, discussion_id=discussion_id)
        session["discussions"][discussion_id] = new_discussion
        session["discussion_titles"][discussion_id] = new_discussion.title
        save_user_discussion(username, discussion_id, new_discussion)
        return new_discussion
    return None

def save_user_discussion(username: str, discussion_id: str, discussion_obj: AppLollmsDiscussion) -> None:
    try: uuid.UUID(discussion_id)
    except ValueError: return
    safe_discussion_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_discussion_filename.endswith(".yaml") or safe_discussion_filename == ".yaml": return
    file_path = get_user_discussion_path(username) / safe_discussion_filename
    try:
        discussion_obj.save_to_disk(file_path)
        if username in user_sessions: user_sessions[username]["discussion_titles"][discussion_id] = discussion_obj.title
    except Exception as e: traceback.print_exc()


# --- Root and Static File Endpoints ---
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index_html(request: Request) -> FileResponse:
    index_path = Path("index.html").resolve()
    if not index_path.is_file(): raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(index_path)

@app.get("/main.js", include_in_schema=False)
async def serve_main_js(request: Request) -> FileResponse:
    main_js_path = Path("main.js").resolve()
    if not main_js_path.is_file(): raise HTTPException(status_code=404, detail="main.js not found.")
    return FileResponse(main_js_path, media_type="application/javascript")
@app.get("/style.css", include_in_schema=False)
async def serve_style_css(request: Request) -> FileResponse:
    style_css_path = Path("style.css").resolve()
    if not style_css_path.is_file(): raise HTTPException(status_code=404, detail="style.css not found.")
    return FileResponse(style_css_path, media_type="text/css")

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def serve_admin_panel_page(admin_user: UserAuthDetails = Depends(get_current_admin_user)) -> FileResponse:
    admin_html_path = Path("admin.html").resolve()
    if not admin_html_path.is_file(): raise HTTPException(status_code=404, detail="admin.html not found.")
    return FileResponse(admin_html_path)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    favicon_path = Path("favicon.ico").resolve()
    return FileResponse(favicon_path, media_type="image/x-icon") if favicon_path.is_file() else Response(status_code=204)

@app.get("/logo.png", include_in_schema=False)
async def logo() -> Response:
    logo_path = Path("logo.png").resolve()
    return FileResponse(logo_path, media_type="image/png") if logo_path.is_file() else Response(status_code=404)

# Serve discussion assets (uploaded images)
user_assets_path_base = APP_DATA_DIR # Used to construct full path for StaticFiles
# Mount dynamically if needed, or ensure user_assets_path_base/<username>/discussion_assets exists
# For simplicity, assuming /user_assets/<username>/<discussion_id>/<filename> structure client-side
# This requires a more dynamic way to serve files or a wildcard path.
# For now, let client fetch from a dedicated endpoint if needed, or keep images as base64 in YAML (not ideal).
# Let's make a dedicated endpoint.

@app.get("/user_assets/{username}/{discussion_id}/{filename}", include_in_schema=False)
async def get_discussion_asset(
    username: str, discussion_id: str, filename: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> FileResponse:
    # Security: Ensure the currently logged-in user is requesting their own asset
    # or an asset from a discussion they have access to (if sharing discussions is implemented broadly)
    if current_user.username != username:
        # Basic check: If a more complex sharing model for discussions is added, this needs adjustment
        raise HTTPException(status_code=403, detail="Forbidden to access assets of another user.")

    asset_path = get_user_discussion_assets_path(username) / discussion_id / secure_filename(filename)
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(asset_path)


try:
    locales_path = Path("locals").resolve()
    if locales_path.is_dir(): app.mount("/locals", StaticFiles(directory=locales_path, html=False), name="locals")
    else: print("WARNING: 'locals' directory not found. Localization files will not be served.")
except Exception as e: print(f"ERROR: Failed to mount locals directory: {e}")

# --- Authentication API ---
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
@auth_router.get("/me", response_model=UserAuthDetails)
async def get_my_details(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails: return current_user
# New endpoint for updating user settings
@auth_router.put("/me", response_model=UserAuthDetails) # Returns the updated user details
async def update_my_details(
    user_update_data: UserUpdate,
    db_user: DBUser = Depends(get_current_db_user), # Get the DBUser object
    db: Session = Depends(get_db)
) -> UserAuthDetails:
    updated_fields = user_update_data.model_dump(exclude_unset=True)
    session_needs_refresh = False
    lollms_client_needs_reinit = False

    for field, value in updated_fields.items():
        if hasattr(db_user, field):
            setattr(db_user, field, value)
            if field == "active_personality_id":
                session_needs_refresh = True
            if field in ["lollms_model_name", "llm_temperature", "llm_top_k", "llm_top_p", "llm_repeat_penalty", "llm_repeat_last_n", "put_thoughts_in_context"]:
                lollms_client_needs_reinit = True # Some LLM params might require client re-init
                session_needs_refresh = True # Also refresh session for these

    try:
        db.commit()
        db.refresh(db_user)

        # Update session if critical fields changed
        if session_needs_refresh and db_user.username in user_sessions:
            session = user_sessions[db_user.username]
            if "active_personality_id" in updated_fields:
                session["active_personality_id"] = db_user.active_personality_id
                if db_user.active_personality_id:
                    active_pers_prompt = db.query(DBPersonality.prompt_text).filter(DBPersonality.id == db_user.active_personality_id).scalar()
                    session["active_personality_prompt"] = active_pers_prompt
                else:
                    session["active_personality_prompt"] = None
            
            # Update session llm_params (non-prefixed keys)
            session_llm_params = session.get("llm_params", {})
            if "llm_temperature" in updated_fields: session_llm_params["temperature"] = db_user.llm_temperature
            if "llm_top_k" in updated_fields: session_llm_params["top_k"] = db_user.llm_top_k
            if "llm_top_p" in updated_fields: session_llm_params["top_p"] = db_user.llm_top_p
            if "llm_repeat_penalty" in updated_fields: session_llm_params["repeat_penalty"] = db_user.llm_repeat_penalty
            if "llm_repeat_last_n" in updated_fields: session_llm_params["repeat_last_n"] = db_user.llm_repeat_last_n
            if "put_thoughts_in_context" in updated_fields: session_llm_params["put_thoughts_in_context"] = db_user.put_thoughts_in_context
            
            session["llm_params"] = {k: v for k, v in session_llm_params.items() if v is not None}

            if "lollms_model_name" in updated_fields:
                session["lollms_model_name"] = db_user.lollms_model_name
                lollms_client_needs_reinit = True
         
            if lollms_client_needs_reinit:
                session["lollms_client"] = None # Force re-init on next use

        # Re-fetch UserAuthDetails to reflect all changes
        # This is a bit inefficient as it re-runs get_current_active_user logic,
        # but ensures consistency.
        # A more direct way would be to construct UserAuthDetails from db_user and session here.
        # For now, let's rely on a fresh call to get_current_active_user by the client after this.
        # Or, we can construct it manually:
        
        lc = get_user_lollms_client(db_user.username) # Ensure client is available for ai_name
        ai_name_for_user = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))
        current_session_llm_params = user_sessions[db_user.username].get("llm_params", {})


        return UserAuthDetails(
            username=db_user.username, is_admin=db_user.is_admin,
            first_name=db_user.first_name, family_name=db_user.family_name,
            email=db_user.email, birth_date=db_user.birth_date,
            lollms_model_name=db_user.lollms_model_name,
            safe_store_vectorizer=db_user.safe_store_vectorizer,
            active_personality_id=db_user.active_personality_id,
            lollms_client_ai_name=ai_name_for_user,
            llm_temperature=current_session_llm_params.get("temperature"),
            llm_top_k=current_session_llm_params.get("top_k"),
            llm_top_p=current_session_llm_params.get("top_p"),
            llm_repeat_penalty=current_session_llm_params.get("repeat_penalty"),
            llm_repeat_last_n=current_session_llm_params.get("repeat_last_n"),
            put_thoughts_in_context=current_session_llm_params.get("put_thoughts_in_context"),
            rag_top_k=db_user.rag_top_k,
            rag_use_graph=db_user.rag_use_graph,
            rag_graph_response_type=db_user.rag_graph_response_type
        )

    except IntegrityError as e:
        db.rollback()
        # Check for specific constraint violations if needed, e.g., unique email
        raise HTTPException(status_code=400, detail=f"Data integrity error: {e.orig}")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@auth_router.post("/logout")
async def logout(response: Response, current_user: UserAuthDetails = Depends(get_current_active_user), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    username = current_user.username
    if username in user_sessions:
        # Clean up temp uploads for the user
        temp_dir = get_user_temp_uploads_path(username)
        if temp_dir.exists():
            background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)
        
        # Close any open SafeStore instances for this user
        # This might be too aggressive if other sessions are active, but for single-session logout it's okay
        # More robust: reference counting or explicit close on instance when no longer needed.
        if "safe_store_instances" in user_sessions[username]:
            for ds_id, ss_instance in user_sessions[username]["safe_store_instances"].items():
                if hasattr(ss_instance, 'close') and callable(ss_instance.close):
                    try: background_tasks.add_task(ss_instance.close)
                    except Exception as e_ss_close: print(f"Error closing SafeStore {ds_id} for {username} on logout: {e_ss_close}")
        
        del user_sessions[username]
        print(f"INFO: User '{username}' session cleared (logged out). Temp files scheduled for cleanup.")
    return {"message": "Logout successful. Session cleared."}


@auth_router.post("/change-password")
async def change_user_password(
    payload: UserPasswordChange,
    db_user_record: DBUser = Depends(get_current_db_user), # Directly get the DBUser object
    db: Session = Depends(get_db) # Still need the session for commit
) -> Dict[str, str]:
    if not db_user_record.verify_password(payload.current_password):
        raise HTTPException(status_code=400, detail="Incorrect current password.")

    if payload.current_password == payload.new_password: # Check if new pass is same as old
        raise HTTPException(status_code=400, detail="New password cannot be the same as the current password.")
        
    db_user_record.hashed_password = hash_password(payload.new_password)

    try:
        # db.add(db_user_record) # Not strictly necessary if object is already session-managed
        db.commit()
        return {"message": "Password changed successfully."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

app.include_router(auth_router)

# --- Image Upload API ---
upload_router = APIRouter(prefix="/api/upload", tags=["Uploads"])
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_UPLOADS_PER_MESSAGE = 5

@upload_router.post("/chat_image", response_model=List[Dict[str,str]])
async def upload_chat_images(
    files: List[UploadFile] = File(...),
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> List[Dict[str,str]]:
    if len(files) > MAX_IMAGE_UPLOADS_PER_MESSAGE:
        raise HTTPException(status_code=400, detail=f"Cannot upload more than {MAX_IMAGE_UPLOADS_PER_MESSAGE} images at once.")

    username = current_user.username
    temp_uploads_path = get_user_temp_uploads_path(username)
    temp_uploads_path.mkdir(parents=True, exist_ok=True)
    
    uploaded_file_infos = []

    for file_upload in files:
        if not file_upload.content_type or not file_upload.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"File '{file_upload.filename}' is not a valid image type.")
        
        # Check file size
        file_upload.file.seek(0, os.SEEK_END)
        file_size = file_upload.file.tell()
        if file_size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"Image '{file_upload.filename}' exceeds max size of {MAX_IMAGE_SIZE_MB}MB.")
        file_upload.file.seek(0) # Reset file pointer

        s_filename_base = secure_filename(Path(file_upload.filename or "uploaded_image").stem)
        s_filename_ext = secure_filename(Path(file_upload.filename or ".png").suffix)
        if not s_filename_ext: s_filename_ext = ".png" # default extension
        
        unique_id = uuid.uuid4().hex[:8]
        final_filename = f"{s_filename_base}_{unique_id}{s_filename_ext}"
        target_file_path = temp_uploads_path / final_filename
        
        try:
            with open(target_file_path, "wb") as buffer:
                shutil.copyfileobj(file_upload.file, buffer)
            
            # Relative path for client to send back, server will resolve later
            relative_server_path = f"{TEMP_UPLOADS_DIR_NAME}/{final_filename}"
            uploaded_file_infos.append({"filename": file_upload.filename, "server_path": relative_server_path})
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not save uploaded image '{file_upload.filename}': {str(e)}")
        finally:
            await file_upload.close()
            
    return uploaded_file_infos
app.include_router(upload_router)


# --- Discussion API ---
discussion_router = APIRouter(prefix="/api/discussions", tags=["Discussions"])

@discussion_router.get("", response_model=List[DiscussionInfo])
async def list_all_discussions(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DiscussionInfo]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found in DB.")
    
    session_discussions = user_sessions[username].get("discussions", {})
    starred_ids = {star.discussion_id for star in db.query(UserStarredDiscussion.discussion_id).filter(UserStarredDiscussion.user_id == user_id).all()}
    
    infos = []
    for disc_id, disc_obj in session_discussions.items():
        infos.append(DiscussionInfo(
            id=disc_id, title=disc_obj.title, 
            is_starred=(disc_id in starred_ids),
            rag_datastore_id=disc_obj.rag_datastore_id
        ))
    return infos

@discussion_router.post("", response_model=DiscussionInfo, status_code=201)
async def create_new_discussion(current_user: UserAuthDetails = Depends(get_current_active_user)) -> DiscussionInfo:
    username = current_user.username
    discussion_id = str(uuid.uuid4())
    discussion_obj = get_user_discussion(username, discussion_id, create_if_missing=True)
    if not discussion_obj: raise HTTPException(status_code=500, detail="Failed to create new discussion.")
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=False, rag_datastore_id=None)

@discussion_router.get("/{discussion_id}", response_model=List[MessageOutput])
async def get_messages_for_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[MessageOutput]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    user_grades_for_discussion = {
        grade.message_id: grade.grade
        for grade in db.query(UserMessageGrade.message_id, UserMessageGrade.grade)
        .filter(UserMessageGrade.user_id == user_id, UserMessageGrade.discussion_id == discussion_id).all()
    }
    messages_output = []
    for msg in discussion_obj.messages:
        # Construct full URL for image assets if any
        full_image_refs = []
        if msg.image_references:
            for ref in msg.image_references:
                # Assuming ref is like "discussion_assets_dir_name/discussion_id/image_filename"
                # or just "image_filename" if stored directly under discussion_assets/discussion_id
                # Client-side, it will request /user_assets/<username>/<discussion_id>/<filename>
                asset_filename = Path(ref).name # Get the filename part
                full_image_refs.append(f"/user_assets/{username}/{discussion_obj.discussion_id}/{asset_filename}")

        messages_output.append(
            MessageOutput(
                id=msg.id, sender=msg.sender, content=msg.content,
                parent_message_id=msg.parent_message_id, binding_name=msg.binding_name,
                model_name=msg.model_name, token_count=msg.token_count,
                image_references=full_image_refs, # Use full URLs for client
                user_grade=user_grades_for_discussion.get(msg.id, 0)
            )
        )
    return messages_output

@discussion_router.put("/{discussion_id}/title", response_model=DiscussionInfo)
async def update_discussion_title(discussion_id: str, title_update: DiscussionTitleUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    discussion_obj.title = title_update.title
    save_user_discussion(username, discussion_id, discussion_obj)
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first() is not None
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=is_starred, rag_datastore_id=discussion_obj.rag_datastore_id)

@discussion_router.put("/{discussion_id}/rag_datastore", response_model=DiscussionInfo)
async def update_discussion_rag_datastore(discussion_id: str, update_payload: DiscussionRagDatastoreUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DiscussionInfo:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    if update_payload.rag_datastore_id: # Validate datastore existence and user access
        try: get_safe_store_instance(username, update_payload.rag_datastore_id, db)
        except HTTPException as e:
            if e.status_code == 404 or e.status_code == 403:
                raise HTTPException(status_code=400, detail=f"Invalid or inaccessible RAG datastore ID: {update_payload.rag_datastore_id}")
            raise e # Re-raise other HTTPExceptions
        except Exception as e_val:
             raise HTTPException(status_code=500, detail=f"Error validating RAG datastore: {str(e_val)}")


    discussion_obj.rag_datastore_id = update_payload.rag_datastore_id
    save_user_discussion(username, discussion_id, discussion_obj)
    
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found in DB for star check.") # Should not happen if active_user works
    is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first() is not None
    
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=is_starred, rag_datastore_id=discussion_obj.rag_datastore_id)


@discussion_router.delete("/{discussion_id}", status_code=200)
async def delete_specific_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    username = current_user.username
    try: uuid.UUID(discussion_id)
    except ValueError: raise HTTPException(status_code=400, detail="Invalid discussion ID format.")
    session = user_sessions[username]
    discussion_exists_in_session = discussion_id in session.get("discussions", {})
    safe_filename = secure_filename(f"{discussion_id}.yaml")
    file_path = get_user_discussion_path(username) / safe_filename
    discussion_exists_on_disk = file_path.exists()
    if not discussion_exists_in_session and not discussion_exists_on_disk:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    session.get("discussions", {}).pop(discussion_id, None)
    session.get("discussion_titles", {}).pop(discussion_id, None)
    if discussion_exists_on_disk:
        try: file_path.unlink()
        except OSError as e:
            if file_path.exists(): print(f"ERROR: Failed to delete discussion file {file_path}: {e}")
    # Delete associated assets
    assets_path = get_user_discussion_assets_path(username) / discussion_id
    if assets_path.exists() and assets_path.is_dir():
        background_tasks.add_task(shutil.rmtree, assets_path, ignore_errors=True)

    try:
        db.query(UserStarredDiscussion).filter_by(discussion_id=discussion_id).delete()
        db.query(UserMessageGrade).filter_by(discussion_id=discussion_id).delete()
        db.commit()
    except Exception as e_db:
        db.rollback()
        print(f"ERROR: Failed to delete DB entries for discussion {discussion_id}: {e_db}")
    return {"message": f"Discussion '{discussion_id}' deleted successfully."}

@discussion_router.post("/{discussion_id}/star", status_code=201)
async def star_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    if not get_user_discussion(username, discussion_id): raise HTTPException(status_code=404, detail="Discussion not found.")
    if db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first():
        return {"message": "Discussion already starred."}
    new_star = UserStarredDiscussion(user_id=user_id, discussion_id=discussion_id)
    try: db.add(new_star); db.commit(); return {"message": "Discussion starred successfully."}
    except IntegrityError: db.rollback(); return {"message": "Discussion already starred (race condition handled)."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"Database error: {e}")

@discussion_router.delete("/{discussion_id}/star", status_code=200)
async def unstar_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    star_to_delete = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first()
    if not star_to_delete: return {"message": "Discussion was not starred."}
    try: db.delete(star_to_delete); db.commit(); return {"message": "Discussion unstarred successfully."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"Database error: {e}")

@discussion_router.post("/{discussion_id}/chat")
async def chat_in_existing_discussion(
    discussion_id: str, prompt: str = Form(...),
    image_server_paths_json: str = Form("[]"), # JSON string of server_paths from upload
    use_rag: bool = Form(False),
    rag_datastore_id: Optional[str] = Form(None), # Datastore to use if RAG is active
    parent_message_id: Optional[str] = Form(None),
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()
) -> StreamingResponse:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    lc = get_user_lollms_client(username)
    
    # Process and persist uploaded images
    final_image_references_for_message: List[str] = []
    llm_image_paths: List[str] = [] # Absolute paths for LollmsClient

    try: image_server_paths = json.loads(image_server_paths_json)
    except json.JSONDecodeError: raise HTTPException(status_code=400, detail="Invalid image_server_paths_json format.")

    if image_server_paths:
        user_temp_uploads_path = get_user_temp_uploads_path(username)
        discussion_assets_path = get_user_discussion_assets_path(username) / discussion_id
        discussion_assets_path.mkdir(parents=True, exist_ok=True)

        for temp_rel_path in image_server_paths:
            if not temp_rel_path.startswith(TEMP_UPLOADS_DIR_NAME + "/"):
                print(f"WARNING: Invalid temporary image path format: {temp_rel_path}")
                continue
            
            image_filename = Path(temp_rel_path).name
            temp_abs_path = user_temp_uploads_path / image_filename
            
            if temp_abs_path.is_file():
                persistent_filename = f"{uuid.uuid4().hex[:8]}_{image_filename}"
                persistent_abs_path = discussion_assets_path / persistent_filename
                try:
                    shutil.move(str(temp_abs_path), str(persistent_abs_path))
                    final_image_references_for_message.append(persistent_filename)
                    llm_image_paths.append(str(persistent_abs_path))
                except Exception as e_move:
                    print(f"ERROR moving image {temp_abs_path} to {persistent_abs_path}: {e_move}")
            else:
                print(f"WARNING: Temporary image file not found: {temp_abs_path}")
    
    user_token_count = lc.binding.count_tokens(prompt) if prompt else 0
    discussion_obj.add_message(
        sender=lc.user_name, content=prompt, parent_message_id=parent_message_id,
        token_count=user_token_count, image_references=final_image_references_for_message
    )

    final_prompt_for_llm = prompt
    if use_rag and safe_store:
        if not rag_datastore_id:
            rag_datastore_id = discussion_obj.rag_datastore_id
            if not rag_datastore_id:
                # Fallback to user's default datastore is not implemented here,
                # user_sessions[username].get("active_vectorizer") is actually the default vectorizer name, not datastore_id.
                # For RAG, a datastore must be selected for the discussion or explicitly passed.
                print(f"WARNING: RAG requested by {username} but no datastore specified for discussion.")


        if rag_datastore_id:
            try:
                ss = get_safe_store_instance(username, rag_datastore_id, db)
                # User's default vectorizer from their settings or global default.
                # This is for querying; documents are added with a specific vectorizer.
                # SafeStore can query using any vectorizer it has embeddings for.
                # If not specified, SafeStore might use its own default or the one most docs are vectorized with.
                # For now, let's rely on SafeStore's internal logic if vectorizer_name is None for query.
                # Or, use the user's preferred one IF the datastore has it.
                active_vectorizer_for_store = user_sessions[username].get("active_vectorizer") # This is the name of vectorizer model, not datastore
                
                # Let's generate a more focused RAG query
                rag_query_prompt = f"Based on the user's question: '{prompt}', formulate a concise search query to find relevant information in a document database. The query should be a few keywords or a short natural language question. Output only the search query itself."
                try:
                    # Note: LollmsClient.generate_text might be better than generate_code for this type of query generation
                    # For simplicity, using existing structure. Revisit if query generation is poor.
                    # This call needs to be non-streaming.
                    query = lc.generate_text(prompt=rag_query_prompt, stream=False, n_predict=250) # Assuming generate_text is available and non-streaming works
                    if isinstance(query, dict) and "generated_text" in query: # Adjust if LollmsClient non-stream returns differently
                        query = query["generated_text"].strip()
                    elif not isinstance(query, str): # Fallback if generate_text returns something unexpected
                         query = prompt # Use original prompt as fallback query
                    print(f"INFO: Generated RAG query: '{query}'")
                except Exception as e_query_gen:
                    print(f"ERROR: Failed to generate RAG query: {e_query_gen}. Using original prompt as query.")
                    query = prompt


                with ss: rag_results = ss.query(query, vectorizer_name=active_vectorizer_for_store, top_k=10) # Use user's default vectorizer for querying
                if rag_results:
                    context_str = "\n\nRelevant context from documents:\n"; 
                    max_rag_len, current_rag_len, sources = 80000, 0, set() # TODO: Make max_rag_len configurable
                    for i, res in enumerate(rag_results):
                        chunk_text = res.get('chunk_text',''); file_name = Path(res.get('file_path','?')).name
                        if current_rag_len + len(chunk_text) > max_rag_len and i > 0: context_str += f"... (truncated {len(rag_results) - i} more results)\n"; break
                        context_str += f"{i+1}. From '{file_name}': {chunk_text}\n"; current_rag_len += len(chunk_text); sources.add(file_name)
                    final_prompt_for_llm = (f"User question: {prompt}\n\n"
                                           f"Use the following context from ({', '.join(sorted(list(sources)))}) to answer if relevant:\n{context_str.strip()}\n\n"
                                           "Answer the user's question based *only* on the provided context. If the context does not contain the answer, state that. Cite sources by filename if multiple are present."
                                           ) # Simplified RAG instruction
                else:
                     print(f"INFO: RAG query for '{query}' on datastore {rag_datastore_id} yielded no results.")
            except HTTPException as e_rag_access: 
                print(f"INFO: RAG query skipped for {username} on datastore {rag_datastore_id}: {e_rag_access.detail}")
            except Exception as e: 
                print(f"ERROR: RAG query failed for {username} on datastore {rag_datastore_id}: {e}")
                traceback.print_exc()
        else: print(f"WARNING: RAG requested by {username} but no RAG datastore selected for this discussion.")
    elif use_rag and not safe_store: print(f"WARNING: RAG requested by {username} but safe_store is not available.")


    main_loop = asyncio.get_event_loop()
    stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

    stop_event = threading.Event()
    shared_state = {
        "accumulated_ai_response": "", 
        "generation_error": None, 
        "final_message_id": None, 
        "binding_name": None, 
        "model_name": None,
        "stop_event": stop_event 
    }

    if username not in user_sessions: user_sessions[username] = {} 
    user_sessions[username].setdefault("active_generation_control", {})[discussion_id] = stop_event

    async def stream_generator() -> AsyncGenerator[str, None]:
        generation_thread: Optional[threading.Thread] = None 
        
        def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict[str, Any]] = None) -> bool:
            if shared_state["stop_event"].is_set():
                stop_message_payload = json.dumps({"type": "info", "content": "Generation stopped by user."}) + "\n"
                if main_loop.is_running(): 
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, stop_message_payload)
                else:
                    print(f"WARNING: asyncio loop not running when trying to send stop message for {username}/{discussion_id}")
                print(f"INFO: LLM Callback for {username}/{discussion_id} detected stop signal. Halting generation.")
                return False 

            if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                shared_state["accumulated_ai_response"] += chunk
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "chunk", "content": chunk}) + "\n")
            elif msg_type in (MSG_TYPE.MSG_TYPE_EXCEPTION, MSG_TYPE.MSG_TYPE_ERROR):
                err_content = f"LLM Error: {str(chunk)}"
                shared_state["generation_error"] = err_content
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_content}) + "\n")
                return False
            elif msg_type == MSG_TYPE.MSG_TYPE_FULL_INVISIBLE_TO_USER:
                if params and "final_message_id" in params: shared_state["final_message_id"] = params["final_message_id"]
            elif msg_type == MSG_TYPE.MSG_TYPE_FINISHED_MESSAGE: return False
            return True

        try: 
            
            
            def blocking_call():
                try:
                    # Fetch active personality prompt from user's session
                    active_personality_prompt_text = user_sessions[username].get("active_personality_prompt")
                    user_puts_thoughts_in_context = user_sessions[username].get("llm_params", {}).get("put_thoughts_in_context", False)

                    shared_state["binding_name"] = lc.binding.binding_name if lc.binding else "unknown_binding"
                    shared_state["model_name"] = lc.binding.model_name if lc.binding and hasattr(lc.binding, "model_name") else user_sessions[username].get("lollms_model_name", "unknown_model")
                    
                    # Prepare the main prompt (history + current user input)
                    main_prompt_content = discussion_obj.prepare_query_for_llm(
                        final_prompt_for_llm # This is the user's current text input, possibly augmented by RAG
                        # max_total_tokens can be passed if needed, or rely on LollmsClient defaults
                    )
                    if not user_puts_thoughts_in_context:
                        main_prompt_content = lc.remove_thinking_blocks(main_prompt_content)
                    
                    # Call generate_text with the separate system_prompt parameter
                    lc.generate_text(
                        prompt=main_prompt_content,
                        system_prompt=active_personality_prompt_text, # Pass system prompt here
                        images=llm_image_paths, 
                        stream=True, 
                        streaming_callback=llm_callback
                        # Other parameters like temperature, top_k, etc., are assumed to be set
                        # on the LollmsClient instance itself or can be overridden here if needed.
                    )
                except Exception as e_gen:
                    err_msg = f"LLM generation failed: {str(e_gen)}"
                    shared_state["generation_error"] = err_msg
                    if main_loop.is_running():
                            main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
                    traceback.print_exc() 
                finally: 
                    if main_loop.is_running():
                        main_loop.call_soon_threadsafe(stream_queue.put_nowait, None) 
            
            generation_thread = threading.Thread(target=blocking_call, daemon=True)
            generation_thread.start()

            while True:
                item = await stream_queue.get()
                if item is None: stream_queue.task_done(); break
                yield item; stream_queue.task_done()
            
            if generation_thread: generation_thread.join(timeout=10) 

            ai_response_content = shared_state["accumulated_ai_response"]
            ai_token_count = lc.binding.count_tokens(ai_response_content) if ai_response_content else 0
            ai_parent_id = discussion_obj.messages[-1].id if discussion_obj.messages and discussion_obj.messages[-1].sender == lc.user_name else None

            if ai_response_content and not shared_state["generation_error"]:
                if shared_state["stop_event"].is_set():
                    print(f"INFO: Saving partial AI response for {username}/{discussion_id} as generation was stopped.")
                
                ai_message = discussion_obj.add_message(
                    sender=lc.ai_name, content=ai_response_content, parent_message_id=ai_parent_id,
                    binding_name=shared_state.get("binding_name"), model_name=shared_state.get("model_name"),
                    token_count=ai_token_count
                )
                if shared_state.get("final_message_id"): ai_message.id = shared_state["final_message_id"]
            elif shared_state["generation_error"]:
                 discussion_obj.add_message(sender="system", content=shared_state["generation_error"], parent_message_id=ai_parent_id)
            
            save_user_discussion(username, discussion_id, discussion_obj)

        except Exception as e_outer:
            error_msg = f"Chat stream error: {str(e_outer)}"; traceback.print_exc()
            try: discussion_obj.add_message(sender="system", content=error_msg); save_user_discussion(username, discussion_id, discussion_obj)
            except Exception as save_err: print(f"ERROR: Failed to save discussion after outer stream error: {save_err}")
            yield json.dumps({"type": "error", "content": error_msg}) + "\n"
        finally:
            if username in user_sessions and "active_generation_control" in user_sessions[username]:
                active_gen_control = user_sessions[username]["active_generation_control"]
                if discussion_id in active_gen_control and active_gen_control.get(discussion_id) == stop_event:
                    del active_gen_control[discussion_id]
                if not active_gen_control: 
                    del user_sessions[username]["active_generation_control"]
            
            if generation_thread and generation_thread.is_alive(): 
                print(f"WARNING: LLM gen thread for {username}/{discussion_id} still alive after stream_generator's main loop. Signaling stop forcefully.")
                if not shared_state["stop_event"].is_set():
                    shared_state["stop_event"].set() 
                generation_thread.join(timeout=5) 
                if generation_thread.is_alive():
                    print(f"CRITICAL: LLM gen thread for {username}/{discussion_id} did not terminate after stop signal and extended wait.")

            if image_server_paths:
                user_temp_uploads_path = get_user_temp_uploads_path(username)
                for temp_rel_path in image_server_paths:
                    image_filename = Path(temp_rel_path).name
                    temp_abs_path = user_temp_uploads_path / image_filename
                    if temp_abs_path.exists(): 
                        background_tasks.add_task(temp_abs_path.unlink, missing_ok=True)

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

@discussion_router.post("/{discussion_id}/stop_generation", status_code=200)
async def stop_discussion_generation(
    discussion_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> Dict[str, str]:
    username = current_user.username
    
    session_data = user_sessions.get(username)
    if not session_data:
        raise HTTPException(status_code=404, detail="User session not found. Cannot process stop generation request.")

    active_gen_control_map = session_data.get("active_generation_control", {})
    stop_event = active_gen_control_map.get(discussion_id)
    
    if stop_event and isinstance(stop_event, threading.Event):
        if not stop_event.is_set():
            stop_event.set()
            print(f"INFO: Stop signal sent for generation in discussion '{discussion_id}' for user '{username}'.")
            return {"message": "Stop signal sent. Generation will attempt to halt."}
        else:
            print(f"INFO: Stop signal for discussion '{discussion_id}' user '{username}' was already set, or generation is completing.")
            return {"message": "Generation is already stopping or has completed."}
    else:
        print(f"INFO: No active generation found to stop for discussion '{discussion_id}' user '{username}'.")
        raise HTTPException(status_code=404, detail="No active generation found for this discussion, or it has already completed and cleaned up.")

@discussion_router.put("/{discussion_id}/messages/{message_id}/grade", response_model=MessageOutput)
async def grade_discussion_message(discussion_id: str, message_id: str, grade_update: MessageGradeUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> MessageOutput:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
    target_message = next((msg for msg in discussion_obj.messages if msg.id == message_id), None)
    if not target_message: raise HTTPException(status_code=404, detail="Message not found in discussion.")
    lc = get_user_lollms_client(username)
    if target_message.sender == lc.user_name: raise HTTPException(status_code=400, detail="User messages cannot be graded.")
    with message_grade_lock:
        grade_record = db.query(UserMessageGrade).filter_by(user_id=user_id, discussion_id=discussion_id, message_id=message_id).first()
        if grade_record: grade_record.grade += grade_update.change
        else: grade_record = UserMessageGrade(user_id=user_id, discussion_id=discussion_id, message_id=message_id, grade=grade_update.change); db.add(grade_record)
        try: db.commit(); db.refresh(grade_record); current_user_grade = grade_record.grade
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error updating grade: {e}")

    full_image_refs = []
    if target_message.image_references:
        for ref in target_message.image_references:
            asset_filename = Path(ref).name
            full_image_refs.append(f"/user_assets/{username}/{discussion_obj.discussion_id}/{asset_filename}")

    return MessageOutput(
        id=target_message.id, sender=target_message.sender, content=target_message.content,
        parent_message_id=target_message.parent_message_id, binding_name=target_message.binding_name,
        model_name=target_message.model_name, token_count=target_message.token_count,
        image_references=full_image_refs, user_grade=current_user_grade
    )

@discussion_router.put("/{discussion_id}/messages/{message_id}", response_model=MessageOutput)
async def update_discussion_message(discussion_id: str, message_id: str, payload: MessageContentUpdate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> MessageOutput:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj or not discussion_obj.edit_message(message_id, payload.content):
        raise HTTPException(status_code=404, detail="Message or discussion not found.")
    save_user_discussion(username, discussion_id, discussion_obj)
    updated_msg = next((m for m in discussion_obj.messages if m.id == message_id), None)
    if not updated_msg: raise HTTPException(status_code=500, detail="Error retrieving updated message.")
    user_grade = 0
    if user_id:
        grade_val = db.query(UserMessageGrade.grade).filter_by(user_id=user_id, discussion_id=discussion_id, message_id=message_id).scalar()
        if grade_val is not None: user_grade = grade_val

    full_image_refs = []
    if updated_msg.image_references:
        for ref in updated_msg.image_references:
            asset_filename = Path(ref).name
            full_image_refs.append(f"/user_assets/{username}/{discussion_obj.discussion_id}/{asset_filename}")
        
    return MessageOutput(
        id=updated_msg.id, sender=updated_msg.sender, content=updated_msg.content,
        parent_message_id=updated_msg.parent_message_id, binding_name=updated_msg.binding_name,
        model_name=updated_msg.model_name, token_count=updated_msg.token_count,
        image_references=full_image_refs, user_grade=user_grade
    )

@discussion_router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
async def delete_discussion_message(discussion_id: str, message_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
    
    message_to_delete = next((msg for msg in discussion_obj.messages if msg.id == message_id), None)
    if not message_to_delete: raise HTTPException(status_code=404, detail="Message not found.")

    image_assets_to_delete = []
    if message_to_delete.image_references:
        disc_assets_path = get_user_discussion_assets_path(username) / discussion_id
        for ref in message_to_delete.image_references:
            asset_path = disc_assets_path / Path(ref).name
            if asset_path.is_file(): image_assets_to_delete.append(asset_path)

    if not discussion_obj.delete_message(message_id): 
        raise HTTPException(status_code=404, detail="Message deletion failed internally.") 
    
    save_user_discussion(username, discussion_id, discussion_obj)
    
    for asset_path in image_assets_to_delete:
        try: asset_path.unlink()
        except OSError as e: print(f"WARN: Could not delete asset file {asset_path}: {e}")

    try:
        db.query(UserMessageGrade).filter_by(discussion_id=discussion_id, message_id=message_id).delete()
        db.commit()
    except Exception as e: db.rollback(); print(f"WARN: Could not delete grades for message {message_id}: {e}")
    return {"message": "Message deleted successfully."}


@discussion_router.post("/{discussion_id}/send", status_code=200)
async def send_discussion_to_user(
    discussion_id: str, send_request: DiscussionSendRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    sender_username = current_user.username
    target_username = send_request.target_username

    if sender_username == target_username:
        raise HTTPException(status_code=400, detail="Cannot send a discussion to yourself.")

    target_user_db = db.query(DBUser).filter(DBUser.username == target_username).first()
    if not target_user_db:
        raise HTTPException(status_code=404, detail=f"Target user '{target_username}' not found.")

    original_discussion_obj = get_user_discussion(sender_username, discussion_id)
    if not original_discussion_obj:
        raise HTTPException(status_code=404, detail=f"Original discussion '{discussion_id}' not found for sender.")

    if target_username not in user_sessions:
        initial_lollms_model_target = target_user_db.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
        llm_params_target_session = { # non-prefixed for session
            "temperature": target_user_db.llm_temperature if target_user_db.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            "top_k": target_user_db.llm_top_k if target_user_db.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
            "top_p": target_user_db.llm_top_p if target_user_db.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
            "repeat_penalty": target_user_db.llm_repeat_penalty if target_user_db.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
            "repeat_last_n": target_user_db.llm_repeat_last_n if target_user_db.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),            
        }
        llm_params_target_session = {k: v for k, v in llm_params_target_session.items() if v is not None}
        user_sessions[target_username] = {
            "lollms_client": None, "safe_store_instances": {}, "discussions": {}, "discussion_titles": {},
            "lollms_model_name": initial_lollms_model_target, "llm_params": llm_params_target_session,
            "active_vectorizer": target_user_db.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
        }
        _load_user_discussions(target_username) 

    target_lc = get_user_lollms_client(target_username) 
    new_discussion_id_for_target = str(uuid.uuid4())
    
    copied_discussion_obj = AppLollmsDiscussion(
        lollms_client_instance=target_lc,
        discussion_id=new_discussion_id_for_target,
        title=f"Sent: {original_discussion_obj.title}"
    )
    copied_discussion_obj.rag_datastore_id = None 

    sender_assets_path = get_user_discussion_assets_path(sender_username) / discussion_id
    target_assets_path = get_user_discussion_assets_path(target_username) / new_discussion_id_for_target
    
    if original_discussion_obj.messages:
        if sender_assets_path.exists() and any(msg.image_references for msg in original_discussion_obj.messages):
            target_assets_path.mkdir(parents=True, exist_ok=True)

    for msg in original_discussion_obj.messages:
        new_image_refs = []
        if msg.image_references:
            for img_ref_filename in msg.image_references: 
                original_asset_file = sender_assets_path / img_ref_filename
                if original_asset_file.exists():
                    new_asset_filename = f"{uuid.uuid4().hex[:8]}_{img_ref_filename}" 
                    target_asset_file = target_assets_path / new_asset_filename
                    try:
                        shutil.copy2(str(original_asset_file), str(target_asset_file))
                        new_image_refs.append(new_asset_filename) 
                    except Exception as e_copy_asset:
                        print(f"ERROR copying asset {original_asset_file} for discussion send: {e_copy_asset}")
                else:
                    print(f"WARN: Asset {original_asset_file} for discussion send not found, skipping.")
        
        copied_discussion_obj.add_message(
            sender=msg.sender, content=msg.content,
            parent_message_id=msg.parent_message_id, 
            binding_name=msg.binding_name, model_name=msg.model_name,
            token_count=msg.token_count, image_references=new_image_refs
        )

    save_user_discussion(target_username, new_discussion_id_for_target, copied_discussion_obj)
    if target_username in user_sessions:
         user_sessions[target_username]["discussions"][new_discussion_id_for_target] = copied_discussion_obj
         user_sessions[target_username]["discussion_titles"][new_discussion_id_for_target] = copied_discussion_obj.title

    return {"message": f"Discussion '{original_discussion_obj.title}' sent to user '{target_username}'."}


@discussion_router.post("/export", response_model=ExportData)
async def export_user_data(export_request: DiscussionExportRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> ExportData:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")

    # User settings are stored with llm_ prefix in DB, export them as is.
    user_settings = {
        "lollms_model_name": user_db_record.lollms_model_name,
        "safe_store_vectorizer": user_db_record.safe_store_vectorizer,
        "llm_temperature": user_db_record.llm_temperature,
        "llm_top_k": user_db_record.llm_top_k,
        "llm_top_p": user_db_record.llm_top_p,
        "llm_repeat_penalty": user_db_record.llm_repeat_penalty,
        "llm_repeat_last_n": user_db_record.llm_repeat_last_n,
    }
    
    owned_datastores_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).all()
    owned_ds_info = [{"id": ds.id, "name": ds.name, "description": ds.description} for ds in owned_datastores_db]
    
    shared_links = db.query(DBSharedDataStoreLink).options(joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner))\
        .filter(DBSharedDataStoreLink.shared_with_user_id == user_db_record.id).all()
    shared_ds_info = [{"id": link.datastore.id, "name": link.datastore.name, "description": link.datastore.description, "owner_username": link.datastore.owner.username} for link in shared_links]

    datastores_export_info = {"owned": owned_ds_info, "shared_with_me": shared_ds_info, "safestore_library_error": None}
    if not safe_store: datastores_export_info["safestore_library_error"] = "SafeStore library not available on server."


    if not user_sessions[username].get("discussions"): _load_user_discussions(username)
    all_user_discussions_map = user_sessions[username].get("discussions", {})
    discussions_to_export_ids = set(all_user_discussions_map.keys())
    if export_request.discussion_ids is not None: discussions_to_export_ids &= set(export_request.discussion_ids)
        
    user_grades_for_export = {}
    if discussions_to_export_ids:
        grades_query = db.query(UserMessageGrade.discussion_id, UserMessageGrade.message_id, UserMessageGrade.grade)\
                         .filter(UserMessageGrade.user_id == user_db_record.id, UserMessageGrade.discussion_id.in_(discussions_to_export_ids)).all()
        for disc_id_db, msg_id_db, grade_db in grades_query:
            if disc_id_db not in user_grades_for_export: user_grades_for_export[disc_id_db] = {}
            user_grades_for_export[disc_id_db][msg_id_db] = grade_db

    discussions_data_list = []
    for disc_id in discussions_to_export_ids:
        disc_obj = all_user_discussions_map.get(disc_id)
        if not disc_obj: continue
        disc_dict = disc_obj.to_dict()
        grades_for_this_disc = user_grades_for_export.get(disc_id, {})
        augmented_messages = []
        for msg_data in disc_dict.get("messages", []):
            msg_id_yaml = msg_data.get("id")
            if msg_id_yaml and msg_id_yaml in grades_for_this_disc:
                msg_data["user_grade"] = grades_for_this_disc[msg_id_yaml]
            augmented_messages.append(msg_data)
        disc_dict["messages"] = augmented_messages
        is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_db_record.id, discussion_id=disc_id).first() is not None
        disc_dict["is_starred"] = is_starred
        discussions_data_list.append(disc_dict)

    return ExportData(
        exported_by_user=username, export_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        application_version=APP_VERSION, user_settings_at_export=user_settings,
        datastores_info=datastores_export_info, discussions=discussions_data_list
    )

@discussion_router.post("/import", status_code=200)
async def import_user_data(import_file: UploadFile = File(...), import_request_json: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, Any]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    try: import_request = DiscussionImportRequest.model_validate_json(import_request_json)
    except Exception as e: raise HTTPException(status_code=400, detail=f"Invalid import request format: {e}")
    if import_file.content_type != "application/json": raise HTTPException(status_code=400, detail="Invalid file type.")
    try: content = await import_file.read(); import_data = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError: raise HTTPException(status_code=400, detail="Invalid JSON file content.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to read upload file: {e}")
    finally: await import_file.close()
    if not isinstance(import_data, dict) or "discussions" not in import_data: raise HTTPException(status_code=400, detail="Invalid export file format.")
    imported_discussions_data = import_data.get("discussions", [])
    if not isinstance(imported_discussions_data, list): raise HTTPException(status_code=400, detail="Format error: 'discussions' not a list.")

    lc = get_user_lollms_client(username); session = user_sessions[username]
    imported_count, skipped_count, errors = 0, 0, []
    if not session.get("discussions"): _load_user_discussions(username)

    imported_user_settings = import_data.get("user_settings_at_export")
    if imported_user_settings:
        print(f"INFO: User settings from import file for user {import_data.get('exported_by_user', 'unknown')}: {imported_user_settings}")
        # Note: Applying imported settings is not done automatically here. 
        # User can set them manually via UI if desired.

    for disc_data_from_file in imported_discussions_data:
        if not isinstance(disc_data_from_file, dict) or "discussion_id" not in disc_data_from_file:
            skipped_count += 1; errors.append({"original_id": "Unknown", "error": "Missing discussion_id in source."}); continue
        original_id = disc_data_from_file["discussion_id"]
        if original_id not in import_request.discussion_ids_to_import: continue
        try:
            new_discussion_id = str(uuid.uuid4())
            imported_discussion_obj = AppLollmsDiscussion(
                lollms_client_instance=lc, discussion_id=new_discussion_id,
                title=disc_data_from_file.get("title", f"Imported {original_id[:8]}")
            )
            imported_discussion_obj.rag_datastore_id = disc_data_from_file.get("rag_datastore_id") 

            messages_from_file = disc_data_from_file.get("messages", [])
            target_assets_path = get_user_discussion_assets_path(username) / new_discussion_id
            
            if isinstance(messages_from_file, list):
                for msg_data_from_file in messages_from_file:
                    if isinstance(msg_data_from_file, dict) and "sender" in msg_data_from_file and "content" in msg_data_from_file:
                        imported_message_obj = AppLollmsMessage.from_dict(msg_data_from_file)
                        imported_message_obj.image_references = [] 
                        imported_discussion_obj.messages.append(imported_message_obj)
                        imported_grade = msg_data_from_file.get("user_grade")
                        if imported_grade is not None and isinstance(imported_grade, int):
                             grade_rec = UserMessageGrade(user_id=user_id, discussion_id=new_discussion_id, message_id=imported_message_obj.id, grade=imported_grade)
                             db.add(grade_rec)
            save_user_discussion(username, new_discussion_id, imported_discussion_obj)
            session["discussions"][new_discussion_id] = imported_discussion_obj
            session["discussion_titles"][new_discussion_id] = imported_discussion_obj.title
            imported_count += 1
            if disc_data_from_file.get("is_starred", False):
                 star_rec = UserStarredDiscussion(user_id=user_id, discussion_id=new_discussion_id)
                 db.add(star_rec)
        except Exception as e_import:
            skipped_count += 1; errors.append({"original_id": original_id, "error": str(e_import)}); traceback.print_exc()
    try: db.commit()
    except Exception as e_db: db.rollback(); errors.append({"DB_COMMIT_ERROR": str(e_db)})
    return {"message": f"Import finished. Imported: {imported_count}, Skipped/Errors: {skipped_count}.", "imported_count": imported_count, "skipped_count": skipped_count, "errors": errors}

app.include_router(discussion_router)

# --- LoLLMs Configuration API ---
lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])
@lollms_config_router.get("/lollms-models", response_model=List[Dict[str, str]])
async def get_available_lollms_models(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[Dict[str, str]]:
    lc = get_user_lollms_client(current_user.username); models_set: set[str] = set()
    try:
        binding_models = lc.listModels()
        if isinstance(binding_models, list):
            for item in binding_models:
                if isinstance(item, str): models_set.add(item)
                elif isinstance(item, dict): name = item.get("name", item.get("id", item.get("model_name"))); models_set.add(name)
    except Exception as e: print(f"WARNING: Could not list models from LollmsClient: {e}")
    user_model = user_sessions[current_user.username].get("lollms_model_name"); global_default_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
    if user_model: models_set.add(user_model)
    if global_default_model: models_set.add(global_default_model)
    models_set.discard(""); models_set.discard(None)
    if not models_set and lc.binding is not None and "openai" in lc.binding.binding_name.lower(): models_set.update(["gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
    return [{"name": name} for name in sorted(list(models_set))] if models_set else [{"name": "No models found"}]

@lollms_config_router.post("/lollms-model") # This sets the user's default model
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    user_sessions[username]["lollms_model_name"] = model_name
    user_sessions[username]["lollms_client"] = None # Force re-init on next use
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user_record:
        db_user_record.lollms_model_name = model_name
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    else: raise HTTPException(status_code=404, detail="User not found for model update.")
    return {"message": f"Default LoLLMs model set to '{model_name}'. Client will re-initialize."}

@lollms_config_router.get("/llm-params", response_model=UserLLMParams)
async def get_user_llm_params(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserLLMParams:
    # UserAuthDetails already contains llm_prefixed params, sourced from session's non-prefixed params
    return UserLLMParams(
        llm_temperature=current_user.llm_temperature,
        llm_top_k=current_user.llm_top_k,
        llm_top_p=current_user.llm_top_p,
        llm_repeat_penalty=current_user.llm_repeat_penalty,
        llm_repeat_last_n=current_user.llm_repeat_last_n,
    )

@lollms_config_router.post("/llm-params")
async def set_user_llm_params(params: UserLLMParams, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not db_user_record: raise HTTPException(status_code=404, detail="User not found.")

    updated_params_in_db = False
    # Update DBUser record with llm_prefixed fields
    if params.llm_temperature is not None and db_user_record.llm_temperature != params.llm_temperature:
        db_user_record.llm_temperature = params.llm_temperature; updated_params_in_db = True
    if params.llm_top_k is not None and db_user_record.llm_top_k != params.llm_top_k:
        db_user_record.llm_top_k = params.llm_top_k; updated_params_in_db = True
    if params.llm_top_p is not None and db_user_record.llm_top_p != params.llm_top_p:
        db_user_record.llm_top_p = params.llm_top_p; updated_params_in_db = True
    if params.llm_repeat_penalty is not None and db_user_record.llm_repeat_penalty != params.llm_repeat_penalty:
        db_user_record.llm_repeat_penalty = params.llm_repeat_penalty; updated_params_in_db = True
    if params.llm_repeat_last_n is not None and db_user_record.llm_repeat_last_n != params.llm_repeat_last_n:
        db_user_record.llm_repeat_last_n = params.llm_repeat_last_n; updated_params_in_db = True

    if updated_params_in_db:
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    
    # Update session llm_params with non-prefixed keys
    session_llm_params = user_sessions[username].get("llm_params", {})
    updated_params_in_session = False

    if params.llm_temperature is not None and session_llm_params.get("temperature") != params.llm_temperature:
        session_llm_params["temperature"] = params.llm_temperature; updated_params_in_session = True
    if params.llm_top_k is not None and session_llm_params.get("top_k") != params.llm_top_k:
        session_llm_params["top_k"] = params.llm_top_k; updated_params_in_session = True
    if params.llm_top_p is not None and session_llm_params.get("top_p") != params.llm_top_p:
        session_llm_params["top_p"] = params.llm_top_p; updated_params_in_session = True
    if params.llm_repeat_penalty is not None and session_llm_params.get("repeat_penalty") != params.llm_repeat_penalty:
        session_llm_params["repeat_penalty"] = params.llm_repeat_penalty; updated_params_in_session = True
    if params.llm_repeat_last_n is not None and session_llm_params.get("repeat_last_n") != params.llm_repeat_last_n:
        session_llm_params["repeat_last_n"] = params.llm_repeat_last_n; updated_params_in_session = True
    
    # Filter out None values from session_llm_params after update
    user_sessions[username]["llm_params"] = {k: v for k, v in session_llm_params.items() if v is not None}

    if updated_params_in_session or updated_params_in_db: # If any change happened
        user_sessions[username]["lollms_client"] = None # Force LollmsClient re-init
        return {"message": "LLM parameters updated. Client will re-initialize."}
        
    return {"message": "No changes to LLM parameters."}

app.include_router(lollms_config_router)


# --- DataStore (RAG) API ---
datastore_router = APIRouter(prefix="/api/datastores", tags=["RAG DataStores"])

@datastore_router.post("", response_model=DataStorePublic, status_code=201)
async def create_datastore(ds_create: DataStoreCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    existing_ds = db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_create.name).first()
    if existing_ds: raise HTTPException(status_code=400, detail=f"DataStore with name '{ds_create.name}' already exists for this user.")

    new_ds_db_obj = DBDataStore(
        owner_user_id=user_db_record.id,
        name=ds_create.name,
        description=ds_create.description
    )
    try:
        db.add(new_ds_db_obj); db.commit(); db.refresh(new_ds_db_obj)
        get_safe_store_instance(current_user.username, new_ds_db_obj.id, db)
        
        return DataStorePublic(
            id=new_ds_db_obj.id, name=new_ds_db_obj.name, description=new_ds_db_obj.description,
            owner_username=current_user.username, created_at=new_ds_db_obj.created_at, updated_at=new_ds_db_obj.updated_at
        )
    except IntegrityError: 
        db.rollback(); raise HTTPException(status_code=400, detail="DataStore name conflict (race condition).")
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error creating datastore: {e}")


@datastore_router.get("", response_model=List[DataStorePublic])
async def list_my_datastores(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DataStorePublic]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first() 
    if not user_db_record: 
        raise HTTPException(status_code=404, detail="User database record not found for authenticated user.") 

    owned_datastores_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).order_by(DBDataStore.name).all()
    
    shared_links_query = db.query(
        DBSharedDataStoreLink, DBDataStore
    ).join(
        DBDataStore, DBSharedDataStoreLink.datastore_id == DBDataStore.id
    ).filter(
        DBSharedDataStoreLink.shared_with_user_id == user_db_record.id 
    ).order_by(
        DBDataStore.name
    )
    shared_links_query = shared_links_query.options(
        joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner)
    )
    
    shared_links_and_datastores_db = shared_links_query.all() 

    response_list = []
    for ds_db in owned_datastores_db:
        response_list.append(DataStorePublic(
            id=ds_db.id, name=ds_db.name, description=ds_db.description,
            owner_username=current_user.username, 
            created_at=ds_db.created_at, updated_at=ds_db.updated_at
        ))
    for link, ds_db in shared_links_and_datastores_db: 
        if not any(r.id == ds_db.id for r in response_list):
             response_list.append(DataStorePublic(
                id=ds_db.id, name=ds_db.name, description=ds_db.description,
                owner_username=ds_db.owner.username, 
                created_at=ds_db.created_at, updated_at=ds_db.updated_at
            ))
    return response_list


@datastore_router.put("/{datastore_id}", response_model=DataStorePublic)
async def update_datastore(datastore_id: str, ds_update: DataStoreBase, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    ds_db_obj = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj: raise HTTPException(status_code=404, detail="DataStore not found.")
    if ds_db_obj.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can update a DataStore.")

    if ds_update.name != ds_db_obj.name:
        existing_ds = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id, DBDataStore.name == ds_update.name, DBDataStore.id != datastore_id).first()
        if existing_ds: raise HTTPException(status_code=400, detail=f"DataStore with name '{ds_update.name}' already exists.")

    ds_db_obj.name = ds_update.name
    ds_db_obj.description = ds_update.description
    try:
        db.commit(); db.refresh(ds_db_obj)
        return DataStorePublic(
             id=ds_db_obj.id, name=ds_db_obj.name, description=ds_db_obj.description,
             owner_username=current_user.username, created_at=ds_db_obj.created_at, updated_at=ds_db_obj.updated_at
        )
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error updating datastore: {e}")


@datastore_router.delete("/{datastore_id}", status_code=200)
async def delete_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    ds_db_obj = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    if not ds_db_obj: raise HTTPException(status_code=404, detail="DataStore not found.")
    if ds_db_obj.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete a DataStore.")
    
    ds_file_path = get_datastore_db_path(current_user.username, datastore_id)
    ds_lock_file_path = Path(f"{ds_file_path}.lock")

    try:
        db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id).delete(synchronize_session=False)
        db.delete(ds_db_obj)
        db.commit()
        
        if current_user.username in user_sessions and datastore_id in user_sessions[current_user.username]["safe_store_instances"]:
            del user_sessions[current_user.username]["safe_store_instances"][datastore_id]

        if ds_file_path.exists(): background_tasks.add_task(ds_file_path.unlink, missing_ok=True)
        if ds_lock_file_path.exists(): background_tasks.add_task(ds_lock_file_path.unlink, missing_ok=True)
            
        return {"message": f"DataStore '{ds_db_obj.name}' deleted successfully."}
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error deleting datastore: {e}")

@datastore_router.post("/{datastore_id}/share", status_code=201)
async def share_datastore(datastore_id: str, share_request: DataStoreShareRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_to_share = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_share: raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")

    target_user_db = db.query(DBUser).filter(DBUser.username == share_request.target_username).first()
    if not target_user_db: raise HTTPException(status_code=404, detail=f"Target user '{share_request.target_username}' not found.")
    
    if owner_user_db.id == target_user_db.id:
        raise HTTPException(status_code=400, detail="Cannot share a datastore with yourself.")

    existing_link = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=target_user_db.id).first()
    if existing_link:
        if existing_link.permission_level != share_request.permission_level:
            existing_link.permission_level = share_request.permission_level
            db.commit()
            return {"message": f"DataStore '{ds_to_share.name}' sharing permission updated for user '{target_user_db.username}'."}
        return {"message": f"DataStore '{ds_to_share.name}' already shared with user '{target_user_db.username}' with this permission."}

    new_link = DBSharedDataStoreLink(
        datastore_id=datastore_id,
        shared_with_user_id=target_user_db.id,
        permission_level=share_request.permission_level
    )
    try:
        db.add(new_link); db.commit()
        return {"message": f"DataStore '{ds_to_share.name}' shared successfully with user '{target_user_db.username}'."}
    except IntegrityError: 
        db.rollback(); raise HTTPException(status_code=400, detail="Sharing conflict (race condition).")
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error sharing datastore: {e}")

@datastore_router.delete("/{datastore_id}/share/{target_user_id_or_username}", status_code=200)
async def unshare_datastore(datastore_id: str, target_user_id_or_username: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    owner_user_db = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not owner_user_db: raise HTTPException(status_code=404, detail="Owner user not found.")

    ds_to_unshare = db.query(DBDataStore).filter(DBDataStore.id == datastore_id, DBDataStore.owner_user_id == owner_user_db.id).first()
    if not ds_to_unshare: raise HTTPException(status_code=404, detail="DataStore not found or you are not the owner.")

    target_user_db = None
    try:
        target_user_id = int(target_user_id_or_username)
        target_user_db = db.query(DBUser).filter(DBUser.id == target_user_id).first()
    except ValueError: 
        target_user_db = db.query(DBUser).filter(DBUser.username == target_user_id_or_username).first()
        
    if not target_user_db: raise HTTPException(status_code=404, detail=f"Target user '{target_user_id_or_username}' not found.")

    link_to_delete = db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id, shared_with_user_id=target_user_db.id).first()
    if not link_to_delete:
        raise HTTPException(status_code=404, detail=f"DataStore was not shared with user '{target_user_db.username}'.")

    try:
        db.delete(link_to_delete); db.commit()
        return {"message": f"DataStore '{ds_to_unshare.name}' unshared from user '{target_user_db.username}'."}
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error unsharing datastore: {e}")

app.include_router(datastore_router)


# --- SafeStore File Management API (now per-datastore) ---
store_files_router = APIRouter(prefix="/api/store/{datastore_id}", tags=["SafeStore RAG & File Management"])

@store_files_router.get("/vectorizers", response_model=List[Dict[str,str]])
async def list_datastore_vectorizers(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[Dict[str,str]]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    try:
        with ss: methods_in_db = ss.list_vectorization_methods(); possible_names = ss.list_possible_vectorizer_names()
        formatted = []; existing_names = set()
        for method_info in methods_in_db:
            name = method_info.get("method_name")
            if name: formatted.append({"name": name, "method_name": f"{name} (dim: {method_info.get('vector_dim', 'N/A')})"}); existing_names.add(name)
        for possible_name in possible_names:
            if possible_name not in existing_names:
                display_text = possible_name
                if possible_name.startswith("tfidf:"): display_text = f"{possible_name} (TF-IDF)"
                elif possible_name.startswith("st:"): display_text = f"{possible_name} (Sentence Transformer)"
                formatted.append({"name": possible_name, "method_name": display_text})
        final_list = []; seen_names = set()
        for fv in formatted:
            if fv["name"] not in seen_names: final_list.append(fv); seen_names.add(fv["name"])
        final_list.sort(key=lambda x: x["name"]); return final_list
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing vectorizers for datastore {datastore_id}: {e}")


@store_files_router.post("/upload-files") 
async def upload_rag_documents_to_datastore(
    datastore_id: str, files: List[UploadFile] = File(...), vectorizer_name: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> JSONResponse:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ds_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not ds_record or not user_db_record or ds_record.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can upload files to this DataStore.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    
    datastore_docs_path = get_user_datastore_root_path(current_user.username) / "safestore_docs" / datastore_id
    datastore_docs_path.mkdir(parents=True, exist_ok=True)

    processed, errors_list = [], []
    try:
        with ss: all_vectorizers = {m['method_name'] for m in ss.list_vectorization_methods()} | set(ss.list_possible_vectorizer_names())
        if not (vectorizer_name in all_vectorizers or vectorizer_name.startswith("st:") or vectorizer_name.startswith("tfidf:")):
             raise HTTPException(status_code=400, detail=f"Vectorizer '{vectorizer_name}' not found or invalid format for datastore {datastore_id}.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error checking vectorizer for datastore {datastore_id}: {e}")

    for file_upload in files:
        s_filename = secure_filename(file_upload.filename or f"upload_{uuid.uuid4().hex[:8]}")
        target_file_path = datastore_docs_path / s_filename
        try:
            with open(target_file_path, "wb") as buffer: shutil.copyfileobj(file_upload.file, buffer)
            with ss: ss.add_document(str(target_file_path), vectorizer_name=vectorizer_name)
            processed.append(s_filename)
        except Exception as e:
            errors_list.append({"filename": s_filename, "error": str(e)}); target_file_path.unlink(missing_ok=True); traceback.print_exc()
        finally: await file_upload.close()
    status_code, msg = (207, "Some files processed with errors.") if errors_list and processed else \
                       (400, "Failed to process uploaded files.") if errors_list else \
                       (200, "All files uploaded and processed successfully.")
    return JSONResponse(status_code=status_code, content={"message": msg, "processed_files": processed, "errors": errors_list})

@store_files_router.get("/files", response_model=List[SafeStoreDocumentInfo])
async def list_rag_documents_in_datastore(datastore_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[SafeStoreDocumentInfo]:
    if not safe_store: return []
    ss = get_safe_store_instance(current_user.username, datastore_id, db) 
    managed_docs = []
    try:
        with ss: stored_meta = ss.list_documents()
        ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
        if not ds_record: raise HTTPException(status_code=404, detail="Datastore metadata not found in main DB.")
        
        expected_docs_root = get_user_datastore_root_path(ds_record.owner.username) / "safestore_docs" / datastore_id
        expected_docs_root_resolved = expected_docs_root.resolve()

        for doc_meta in stored_meta:
            original_path_str = doc_meta.get("file_path")
            if original_path_str:
                try:
                    if Path(original_path_str).resolve().parent == expected_docs_root_resolved:
                        managed_docs.append(SafeStoreDocumentInfo(filename=Path(original_path_str).name))
                except Exception: pass 
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing RAG docs for datastore {datastore_id}: {e}")
    managed_docs.sort(key=lambda x: x.filename); return managed_docs


@store_files_router.delete("/files/{filename}") 
async def delete_rag_document_from_datastore(datastore_id: str, filename: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    ds_record = db.query(DBDataStore).options(joinedload(DBDataStore.owner)).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not ds_record or not user_db_record or ds_record.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete files from this DataStore.")

    s_filename = secure_filename(filename)
    if not s_filename or s_filename != filename: raise HTTPException(status_code=400, detail="Invalid filename.")
    
    datastore_docs_path = get_user_datastore_root_path(current_user.username) / "safestore_docs" / datastore_id
    file_to_delete_path = datastore_docs_path / s_filename
    if not file_to_delete_path.is_file(): raise HTTPException(status_code=404, detail=f"Document '{s_filename}' not found in datastore {datastore_id}.")
    
    ss = get_safe_store_instance(current_user.username, datastore_id, db)
    try:
        with ss: ss.delete_document_by_path(str(file_to_delete_path))
        file_to_delete_path.unlink()
        return {"message": f"Document '{s_filename}' deleted successfully from datastore {datastore_id}."}
    except Exception as e:
        if file_to_delete_path.exists(): raise HTTPException(status_code=500, detail=f"Could not delete '{s_filename}' from datastore {datastore_id}: {e}")
        else: return {"message": f"Document '{s_filename}' file deleted, potential DB cleanup issue in datastore {datastore_id}."}

app.include_router(store_files_router)

# --- Admin API ---
admin_router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(get_current_admin_user)])
@admin_router.get("/users", response_model=List[UserPublic])
async def admin_get_all_users(db: Session = Depends(get_db)) -> List[DBUser]: return db.query(DBUser).all()

@admin_router.post("/users", response_model=UserPublic, status_code=201)
async def admin_add_new_user(user_data: UserCreateAdmin, db: Session = Depends(get_db)) -> DBUser:
    if db.query(DBUser).filter(DBUser.username == user_data.username).first(): raise HTTPException(status_code=400, detail="Username already registered.")
    
    # user_data has llm_prefixed params. DBUser also expects llm_prefixed params.
    # Default values from LOLLMS_CLIENT_DEFAULTS are non-prefixed.
    new_db_user = DBUser(
        username=user_data.username, hashed_password=hash_password(user_data.password), 
        is_admin=user_data.is_admin, 
        lollms_model_name=user_data.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
        safe_store_vectorizer=user_data.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
        llm_temperature=user_data.llm_temperature if user_data.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
        llm_top_k=user_data.llm_top_k if user_data.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
        llm_top_p=user_data.llm_top_p if user_data.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
        llm_repeat_penalty=user_data.llm_repeat_penalty if user_data.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
        llm_repeat_last_n=user_data.llm_repeat_last_n if user_data.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        put_thoughts_in_context=user_data.put_thoughts_in_context if user_data.put_thoughts_in_context is not None else LOLLMS_CLIENT_DEFAULTS.get("put_thoughts_in_context", False)
    )
    try: db.add(new_db_user); db.commit(); db.refresh(new_db_user); return new_db_user
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")

@admin_router.post("/users/{user_id}/reset-password")
async def admin_reset_user_password(user_id: int, payload: UserPasswordResetAdmin, db: Session = Depends(get_db)) -> Dict[str, str]:
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update: raise HTTPException(status_code=404, detail="User not found.")
    user_to_update.hashed_password = hash_password(payload.new_password)
    try: db.commit(); return {"message": f"Password for user '{user_to_update.username}' reset."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")

@admin_router.delete("/users/{user_id}")
async def admin_remove_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user), background_tasks: BackgroundTasks = BackgroundTasks()) -> Dict[str, str]:
    user_to_delete = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_delete: raise HTTPException(status_code=404, detail="User not found.")
    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and user_to_delete.username == initial_admin_username and user_to_delete.is_admin: raise HTTPException(status_code=403, detail="Initial superadmin cannot be deleted.")
    if user_to_delete.username == current_admin.username: raise HTTPException(status_code=403, detail="Administrators cannot delete themselves.")
    
    user_data_dir_to_delete = get_user_data_root(user_to_delete.username) 

    try:
        if user_to_delete.username in user_sessions:
            del user_sessions[user_to_delete.username]

        db.delete(user_to_delete) 
        db.commit()
        
        if user_data_dir_to_delete.exists():
            background_tasks.add_task(shutil.rmtree, user_data_dir_to_delete, ignore_errors=True)
            
        return {"message": f"User '{user_to_delete.username}' and their data deleted."}
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error or file system error during user deletion: {e}")

app.include_router(admin_router)

languages_router = APIRouter(prefix="/api/languages", tags=["Languages router"])
@languages_router.get("/", response_class=JSONResponse)
async def get_languages():
    languages = {}
    if not LOCALS_DIR.is_dir():
        print(f"Warning: Locals directory not found at {LOCALS_DIR}")
        return {"en": "English"}

    try:
        for filepath in LOCALS_DIR.glob("*.json"):
            lang_code = filepath.stem  
            display_name = lang_code.upper()
            if lang_code == "en": display_name = "English"
            elif lang_code == "fr": display_name = "Français"
            elif lang_code == "es": display_name = "Español"
            elif lang_code == "de": display_name = "Deutsch"
            languages[lang_code] = display_name
    except Exception as e:
        print(f"Error scanning locals directory: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve language list.")

    if not languages: 
        print(f"Warning: No JSON language files found in {LOCALS_DIR}")
        return {"en": "English"} 

    return languages

@languages_router.get("/locals/{lang_code}.json")
async def get_locale_file(lang_code: str):
    if not LOCALS_DIR.is_dir():
        raise HTTPException(status_code=404, detail=f"Locals directory not found.")

    if not lang_code.replace('-', '').isalnum():
        raise HTTPException(status_code=400, detail="Invalid language code format.")

    file_path = LOCALS_DIR / f"{lang_code}.json"

    if not file_path.is_file():
        base_lang_code = lang_code.split('-')[0]
        if base_lang_code != lang_code:
            base_file_path = LOCALS_DIR / f"{base_lang_code}.json"
            if base_file_path.is_file():
                print(f"Serving base language file {base_file_path} for requested {file_path}")
                try:
                    with open(base_file_path, "r", encoding="utf-8") as f: content = json.load(f)
                    return JSONResponse(content=content)
                except Exception as e:
                    print(f"Error reading base locale file {base_file_path}: {e}")
                    raise HTTPException(status_code=500, detail="Error reading locale file.")
        raise HTTPException(status_code=404, detail=f"Locale file for '{lang_code}' not found.")

    try:
        with open(file_path, "r", encoding="utf-8") as f: content = json.load(f)
        return JSONResponse(content=content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Locale file '{lang_code}.json' is not valid JSON.")
    except Exception as e:
        print(f"Error reading locale file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error reading locale file.")

app.include_router(languages_router)


# --- Personality Pydantic Models (ensure these are defined) ---
class PersonalityBase(BaseModel):
    name: constr(min_length=1, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    author: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    prompt_text: str 
    disclaimer: Optional[str] = Field(None, max_length=1000)
    script_code: Optional[str] = None
    icon_base64: Optional[str] = None

class PersonalityCreate(PersonalityBase):
    is_public: Optional[bool] = False 

class PersonalityUpdate(PersonalityBase):
    name: Optional[constr(min_length=1, max_length=100)] = None
    prompt_text: Optional[str] = None
    is_public: Optional[bool] = None # Only admin should be able to make an existing one public

class PersonalityPublic(PersonalityBase):
    id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_public: bool
    owner_username: Optional[str] = None 
    model_config = {"from_attributes": True}

# --- FastAPI Router for Personalities ---
personalities_router = APIRouter(prefix="/api/personalities", tags=["Personalities"])

def get_personality_public_from_db(db_personality: DBPersonality, owner_username: Optional[str] = None) -> PersonalityPublic:
    """Helper to convert DBPersonality to PersonalityPublic, fetching owner username if needed."""
    if owner_username is None and db_personality.owner_user_id and db_personality.owner:
        owner_username = db_personality.owner.username
    elif owner_username is None and db_personality.owner_user_id and not db_personality.owner:
        # This case should be rare if relationships are loaded, but as a fallback:
        # db = next(get_db()) # Avoid creating new session if possible
        # owner = db.query(DBUser.username).filter(DBUser.id == db_personality.owner_user_id).scalar()
        # owner_username = owner if owner else "Unknown"
        # db.close()
        # For simplicity, if owner not loaded, it will be None. Caller should ensure owner is loaded.
        pass


    return PersonalityPublic(
        id=db_personality.id,
        name=db_personality.name,
        category=db_personality.category,
        author=db_personality.author,
        description=db_personality.description,
        prompt_text=db_personality.prompt_text,
        disclaimer=db_personality.disclaimer,
        script_code=db_personality.script_code,
        icon_base64=db_personality.icon_base64,
        created_at=db_personality.created_at,
        updated_at=db_personality.updated_at,
        is_public=db_personality.is_public,
        owner_username=owner_username
    )

@personalities_router.post("", response_model=PersonalityPublic, status_code=201)
async def create_personality(
    personality_data: PersonalityCreate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Check for name conflict for this user
    existing_personality = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == db_user.id,
        DBPersonality.name == personality_data.name
    ).first()
    if existing_personality:
        raise HTTPException(status_code=400, detail=f"You already have a personality named '{personality_data.name}'.")

    # If admin tries to create a public personality
    owner_id_for_new_pers = db_user.id
    if personality_data.is_public and current_user.is_admin:
        # Admin can create a truly public (system) personality with no owner,
        # or a public personality owned by themselves.
        # For simplicity, let's assume admin-created public personalities are system-level (owner_user_id = None)
        # Or, if you want admin to "own" public ones they create:
        # owner_id_for_new_pers = db_user.id
        # For truly public/system, set owner_id_for_new_pers = None
        # Let's make admin-created public personalities owned by them for now, simpler.
        pass # is_public will be set from personality_data
    elif personality_data.is_public and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only administrators can create public personalities.")
    
    db_personality = DBPersonality(
        **personality_data.model_dump(exclude={"is_public"}), # Exclude is_public if handled separately
        owner_user_id=owner_id_for_new_pers, # User owns their created personalities
        is_public=personality_data.is_public if current_user.is_admin else False # User-created are private
    )

    try:
        db.add(db_personality)
        db.commit()
        db.refresh(db_personality)
        return get_personality_public_from_db(db_personality, current_user.username)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.get("/my", response_model=List[PersonalityPublic])
async def get_my_personalities(
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> List[PersonalityPublic]:
    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    owned_personalities_db = db.query(DBPersonality).filter(DBPersonality.owner_user_id == db_user.id).order_by(DBPersonality.name).all()
    return [get_personality_public_from_db(p, current_user.username) for p in owned_personalities_db]

@personalities_router.get("/public", response_model=List[PersonalityPublic])
async def get_public_personalities(
    db: Session = Depends(get_db)
    # No auth needed to view public personalities, but could be added if desired
) -> List[PersonalityPublic]:
    # Load owner relationship to get owner_username
    public_personalities_db = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.is_public == True).order_by(DBPersonality.category, DBPersonality.name).all()
    return [get_personality_public_from_db(p) for p in public_personalities_db]


@personalities_router.get("/{personality_id}", response_model=PersonalityPublic)
async def get_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user), # Auth to check ownership for non-public
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).options(joinedload(DBPersonality.owner)).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user: # Should not happen if current_user is valid
        raise HTTPException(status_code=404, detail="Requesting user not found.")

    is_owner = (db_personality.owner_user_id == db_user.id)

    if not db_personality.is_public and not is_owner:
        raise HTTPException(status_code=403, detail="You do not have permission to view this personality.")
    
    return get_personality_public_from_db(db_personality)


@personalities_router.put("/{personality_id}", response_model=PersonalityPublic)
async def update_personality(
    personality_id: str,
    personality_data: PersonalityUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not current_user.is_admin: # Only owner or admin can update
        raise HTTPException(status_code=403, detail="You do not have permission to update this personality.")
    
    # If admin is updating a personality not owned by them, they can change its public status.
    # If user is updating their own, they cannot make it public unless they are also admin.
    if personality_data.is_public is not None:
        if not current_user.is_admin:
            # Non-admin trying to change public status of their own personality
            if is_owner and personality_data.is_public != db_personality.is_public:
                 raise HTTPException(status_code=403, detail="Only administrators can change the public status of a personality.")
        # If admin, they can change is_public for any personality
        # If it's an admin updating their own, they can change it.
        # If it's an admin updating someone else's, they can change it.
        # If it's an admin updating a system (owner_user_id=None) personality, they can change it.
        if current_user.is_admin:
            db_personality.is_public = personality_data.is_public
    
    update_data = personality_data.model_dump(exclude_unset=True, exclude={"is_public"}) # is_public handled above

    if "name" in update_data and update_data["name"] != db_personality.name:
        # Check for name conflict for this user if it's their personality
        # Or global conflict if it's a public personality being renamed by admin
        owner_id_for_check = db_personality.owner_user_id
        if db_personality.is_public and owner_id_for_check is None: # System personality
             existing_conflict = db.query(DBPersonality).filter(
                DBPersonality.owner_user_id == None, # Check among system personalities
                DBPersonality.name == update_data["name"],
                DBPersonality.id != personality_id
            ).first()
        else: # User-owned or admin-owned public
            existing_conflict = db.query(DBPersonality).filter(
                DBPersonality.owner_user_id == owner_id_for_check,
                DBPersonality.name == update_data["name"],
                DBPersonality.id != personality_id
            ).first()
        if existing_conflict:
            raise HTTPException(status_code=400, detail=f"A personality named '{update_data['name']}' already exists.")

    for field, value in update_data.items():
        if hasattr(db_personality, field):
            setattr(db_personality, field, value)
    
    try:
        db.commit()
        db.refresh(db_personality)
        # Reload owner for username if it was an admin editing someone else's
        db.refresh(db_personality, attribute_names=['owner']) 
        return get_personality_public_from_db(db_personality)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Personality name conflict (race condition).")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@personalities_router.delete("/{personality_id}", status_code=200)
async def delete_personality(
    personality_id: str,
    current_user: UserAuthDetails = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    db_personality = db.query(DBPersonality).filter(DBPersonality.id == personality_id).first()
    if not db_personality:
        raise HTTPException(status_code=404, detail="Personality not found.")

    db_user = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    is_owner = (db_personality.owner_user_id == db_user.id)

    if not is_owner and not (current_user.is_admin and db_personality.is_public):
        # User can delete their own.
        # Admin can delete any public personality (even if owned by another user, or system-owned).
        raise HTTPException(status_code=403, detail="You do not have permission to delete this personality.")

    # If this personality is active for any user, set their active_personality_id to None
    users_with_this_active_personality = db.query(DBUser).filter(DBUser.active_personality_id == personality_id).all()
    for user_to_update in users_with_this_active_personality:
        user_to_update.active_personality_id = None
        # Clear from session if user is active
        if user_to_update.username in user_sessions:
            user_sessions[user_to_update.username]["active_personality_id"] = None
            user_sessions[user_to_update.username]["active_personality_prompt"] = None
            # If this affects the current_user, their session will be updated.
            # If it affects other users, their session will update on their next /me or relevant action.

    try:
        db.delete(db_personality)
        db.commit()
        return {"message": f"Personality '{db_personality.name}' deleted successfully."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@personalities_router.post("/{personality_id}/send", response_model=PersonalityPublic)
async def send_personality_to_user(
    personality_id: str,
    send_request: PersonalitySendRequest,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> PersonalityPublic:
    original_personality = db.query(DBPersonality).filter(
        DBPersonality.id == personality_id,
        # User can send their own, or an admin can send any public one
        or_(
            DBPersonality.owner_user_id == current_db_user.id,
            and_(DBPersonality.is_public == True, current_db_user.is_admin == True)
        )
    ).first()

    if not original_personality:
        raise HTTPException(status_code=404, detail="Personality not found or you don't have permission to send it.")

    target_user = db.query(DBUser).filter(DBUser.username == send_request.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"Target user '{send_request.target_username}' not found.")
    
    if target_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot send a personality to yourself.")

    # Check if target user already has a personality with the same name
    existing_target_pers = db.query(DBPersonality).filter(
        DBPersonality.owner_user_id == target_user.id,
        DBPersonality.name == original_personality.name
    ).first()
    if existing_target_pers:
        raise HTTPException(status_code=400, detail=f"User '{target_user.username}' already has a personality named '{original_personality.name}'.")

    copied_personality = DBPersonality(
        name=original_personality.name, # Or prompt for a new name if desired
        category=original_personality.category,
        author=original_personality.author, # Or set to sender: current_db_user.username
        description=original_personality.description,
        prompt_text=original_personality.prompt_text,
        disclaimer=original_personality.disclaimer,
        script_code=original_personality.script_code,
        icon_base64=original_personality.icon_base64,
        owner_user_id=target_user.id, # New owner is the target user
        is_public=False # Copies are private to the recipient
    )
    db.add(copied_personality)
    try:
        db.commit()
        db.refresh(copied_personality)
        return get_personality_public_from_db(copied_personality, target_user.username)
    except IntegrityError: # Should be caught by name check above
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to send personality due to a name conflict for the target user.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error sending personality: {str(e)}")

# Add the router to the main app
app.include_router(personalities_router)

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    host = SERVER_CONFIG.get("host", "127.0.0.1"); port = int(SERVER_CONFIG.get("port", 9642))
    try: APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e: print(f"CRITICAL: Could not create main data directory {APP_DATA_DIR}: {e}")
    print(f"--- Simplified LoLLMs Chat API Server (v{APP_VERSION}) ---")
    print(f"Access UI at: http://{host}:{port}/")
    print(f"Access Admin Panel at: http://{host}:{port}/admin (requires admin login)")
    print("--------------------------------------------------------------------")
    uvicorn.run("main:app", host=host, port=port, reload=False) 

# --- FastAPI Router for Friendships ---
friends_router = APIRouter(prefix="/api/friends", tags=["Friends Management"])

def get_friend_public_from_friendship(friendship: Friendship, current_user_id: int) -> FriendPublic:
    """
    Helper to determine who the 'friend' is in a friendship record
    relative to the current_user_id and format it as FriendPublic.
    """
    friend_user_obj = None
    if friendship.user1_id == current_user_id:
        friend_user_obj = friendship.user2 # The other user is user2
    elif friendship.user2_id == current_user_id:
        friend_user_obj = friendship.user1 # The other user is user1
    
    if not friend_user_obj:
        # This should not happen if the friendship involves the current_user_id
        raise ValueError("Friendship record does not involve the current user.")

    return FriendPublic(
        id=friend_user_obj.id,
        username=friend_user_obj.username,
        friendship_id=friendship.id,
        status_with_current_user=friendship.status # The status of the friendship itself
    )

@friends_router.post("/request", response_model=FriendshipRequestPublic, status_code=201)
async def send_friend_request(
    request_data: FriendRequestCreate,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendshipRequestPublic:
    if current_db_user.username == request_data.target_username:
        raise HTTPException(status_code=400, detail="You cannot send a friend request to yourself.")

    target_user = db.query(DBUser).filter(DBUser.username == request_data.target_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{request_data.target_username}' not found.")

    # Ensure canonical order for user1_id and user2_id to prevent duplicate entries
    # (user1_id < user2_id)
    user1_id, user2_id = sorted((current_db_user.id, target_user.id))

    existing_friendship = db.query(Friendship).filter(
        Friendship.user1_id == user1_id,
        Friendship.user2_id == user2_id
    ).first()

    if existing_friendship:
        if existing_friendship.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="You are already friends with this user.")
        elif existing_friendship.status == FriendshipStatus.PENDING and existing_friendship.action_user_id == current_db_user.id:
            raise HTTPException(status_code=400, detail="You have already sent a friend request to this user.")
        elif existing_friendship.status == FriendshipStatus.PENDING and existing_friendship.action_user_id == target_user.id:
            raise HTTPException(status_code=400, detail="This user has already sent you a friend request. Please respond to it.")
        elif existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and user1_id == current_db_user.id: # You blocked them
            raise HTTPException(status_code=403, detail="You have blocked this user. Unblock them to send a request.")
        elif existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and user2_id == current_db_user.id: # You blocked them
             raise HTTPException(status_code=403, detail="You have blocked this user. Unblock them to send a request.")
        elif (existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and user1_id == target_user.id) or \
             (existing_friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and user2_id == target_user.id): # They blocked you
            raise HTTPException(status_code=403, detail="You cannot send a friend request to this user as they have blocked you.")
        # If other statuses, potentially allow re-request or overwrite (e.g., after a decline)
        # For now, if any record exists and isn't one of the above, it's an edge case or needs specific handling.
        # Let's assume we can overwrite a previously declined/removed one by setting status to PENDING.
        existing_friendship.status = FriendshipStatus.PENDING
        existing_friendship.action_user_id = current_db_user.id # Current user is sending the request
        db_friendship_to_return = existing_friendship
    else:
        new_friendship = Friendship(
            user1_id=user1_id,
            user2_id=user2_id,
            status=FriendshipStatus.PENDING,
            action_user_id=current_db_user.id # Current user is sending the request
        )
        db.add(new_friendship)
        db_friendship_to_return = new_friendship
    
    try:
        db.commit()
        db.refresh(db_friendship_to_return)
        return FriendshipRequestPublic(
            friendship_id=db_friendship_to_return.id,
            requesting_user_id=current_db_user.id, # The one who sent the request
            requesting_username=current_db_user.username,
            requested_at=db_friendship_to_return.created_at, # Or updated_at if overwriting
            status=db_friendship_to_return.status
        )
    except IntegrityError: # Should be caught by existing_friendship check mostly
        db.rollback()
        raise HTTPException(status_code=400, detail="Friendship request conflict.")
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.get("/requests/pending", response_model=List[FriendshipRequestPublic])
async def get_pending_friend_requests(
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> List[FriendshipRequestPublic]:
    """Gets friend requests sent TO the current user that are pending."""
    pending_requests_db = db.query(Friendship).options(
        joinedload(Friendship.user1), # Eager load user1 (potential requester)
        joinedload(Friendship.user2)  # Eager load user2 (potential requester)
    ).filter(
        or_(
            and_(Friendship.user1_id == current_db_user.id, Friendship.action_user_id != current_db_user.id), # Request sent by user2 to user1
            and_(Friendship.user2_id == current_db_user.id, Friendship.action_user_id != current_db_user.id)  # Request sent by user1 to user2
        ),
        Friendship.status == FriendshipStatus.PENDING
    ).all()

    response_list = []
    for req in pending_requests_db:
        requester = req.user1 if req.user2_id == current_db_user.id else req.user2
        if requester: # Ensure requester object is loaded
            response_list.append(FriendshipRequestPublic(
                friendship_id=req.id,
                requesting_user_id=requester.id,
                requesting_username=requester.username,
                requested_at=req.updated_at, # Use updated_at as it reflects when request was made/last actioned
                status=req.status
            ))
    return response_list

@friends_router.put("/requests/{friendship_id}", response_model=FriendPublic)
async def respond_to_friend_request(
    friendship_id: int,
    response_data: FriendshipAction, # e.g., {"action": "accept"} or {"action": "reject"}
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendPublic:
    friendship = db.query(Friendship).filter(Friendship.id == friendship_id).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="Friend request not found.")

    # Ensure the current user is the recipient of this pending request
    is_recipient = (friendship.user1_id == current_db_user.id and friendship.action_user_id != current_db_user.id) or \
                   (friendship.user2_id == current_db_user.id and friendship.action_user_id != current_db_user.id)

    if not is_recipient or friendship.status != FriendshipStatus.PENDING:
        raise HTTPException(status_code=403, detail="Not a valid pending request for you to respond to.")

    action = response_data.action.lower()
    if action == "accept":
        friendship.status = FriendshipStatus.ACCEPTED
        friendship.action_user_id = current_db_user.id # Current user accepted
    elif action == "reject":
        # Option 1: Delete the request
        db.delete(friendship)
        db.commit()
        # Return a specific response or raise an exception that the frontend can interpret as "rejected and removed"
        # For simplicity, let's just say it's gone. The frontend won't see it in pending list.
        # Or, if you want to keep a "declined" state:
        # friendship.status = FriendshipStatus.DECLINED 
        # friendship.action_user_id = current_db_user.id
        # For now, deleting is simpler.
        raise HTTPException(status_code=200, detail="Friend request rejected and removed.") # 200 or 204
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'accept' or 'reject'.")

    try:
        db.commit()
        db.refresh(friendship)
        # Eager load related users for get_friend_public_from_friendship
        db.refresh(friendship, attribute_names=['user1', 'user2'])
        return get_friend_public_from_friendship(friendship, current_db_user.id)
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.get("", response_model=List[FriendPublic]) # Get list of accepted friends
async def get_my_friends(
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> List[FriendPublic]:
    # Friendships where current user is user1 OR user2, and status is ACCEPTED
    friendships_db = db.query(Friendship).options(
        joinedload(Friendship.user1), joinedload(Friendship.user2)
    ).filter(
        or_(Friendship.user1_id == current_db_user.id, Friendship.user2_id == current_db_user.id),
        Friendship.status == FriendshipStatus.ACCEPTED
    ).order_by(Friendship.updated_at.desc()).all() # Or order by friend's username

    friends_list = []
    for fs in friendships_db:
        try:
            friends_list.append(get_friend_public_from_friendship(fs, current_db_user.id))
        except ValueError: # Should not happen with the query filter
            pass 
    
    # Sort by username for consistent display
    friends_list.sort(key=lambda f: f.username.lower())
    return friends_list


@friends_router.delete("/{friend_user_id_or_username}", status_code=200) # Unfriend or cancel sent request
async def remove_friend_or_cancel_request(
    friend_user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    other_user = None
    try:
        other_user_id = int(friend_user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == friend_user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot perform this action on yourself.")

    user1_id, user2_id = sorted((current_db_user.id, other_user.id))

    friendship = db.query(Friendship).filter(
        Friendship.user1_id == user1_id,
        Friendship.user2_id == user2_id
    ).first()

    if not friendship:
        raise HTTPException(status_code=404, detail="No friendship or request found with this user.")

    action_taken = ""
    if friendship.status == FriendshipStatus.ACCEPTED:
        # Unfriend: Delete the record
        db.delete(friendship)
        action_taken = "unfriended"
    elif friendship.status == FriendshipStatus.PENDING and friendship.action_user_id == current_db_user.id:
        # Cancel sent request: Delete the record
        db.delete(friendship)
        action_taken = "friend request cancelled"
    elif friendship.status == FriendshipStatus.PENDING and friendship.action_user_id == other_user.id:
        # Reject incoming request: Delete the record (same as /requests/{id} with "reject")
        db.delete(friendship)
        action_taken = "friend request rejected"
    else:
        # E.g., trying to unfriend someone you blocked, or a non-pending/non-accepted state
        raise HTTPException(status_code=400, detail=f"Cannot perform this action on current friendship status: {friendship.status.value}")

    try:
        db.commit()
        return {"message": f"Successfully {action_taken} user '{other_user.username}'."}
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# --- New Block/Unblock Endpoints ---
@friends_router.put("/block/{user_id_or_username}", response_model=FriendPublic)
async def block_user(
    user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendPublic:
    other_user = None
    try:
        other_user_id_val = int(user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id_val).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="You cannot block yourself.")

    friendship = get_friendship_record(db, current_db_user.id, other_user.id)
    
    user1_id_ordered, user2_id_ordered = sorted((current_db_user.id, other_user.id))

    if not friendship:
        friendship = Friendship(
            user1_id=user1_id_ordered,
            user2_id=user2_id_ordered,
            action_user_id=current_db_user.id
        )
        db.add(friendship)
    else:
        # Check if already blocked by the other user
        if (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == other_user.id) or \
           (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == other_user.id):
            raise HTTPException(status_code=403, detail="Cannot block a user who has blocked you.")
        friendship.action_user_id = current_db_user.id


    if user1_id_ordered == current_db_user.id: # Current user is user1 in the canonical pair
        friendship.status = FriendshipStatus.BLOCKED_BY_USER1
    else: # Current user is user2 in the canonical pair
        friendship.status = FriendshipStatus.BLOCKED_BY_USER2
    
    try:
        db.commit()
        db.refresh(friendship)
        db.refresh(friendship, attribute_names=['user1', 'user2'])
        return get_friend_public_from_friendship(friendship, current_db_user.id)
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@friends_router.put("/unblock/{user_id_or_username}", response_model=FriendPublic)
async def unblock_user(
    user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> FriendPublic:
    other_user = None
    try:
        other_user_id_val = int(user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id_val).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Target user not found.")
    if other_user.id == current_db_user.id: # Should not happen if UI prevents
        raise HTTPException(status_code=400, detail="Invalid action.")

    friendship = get_friendship_record(db, current_db_user.id, other_user.id)

    if not friendship:
        raise HTTPException(status_code=404, detail="No relationship record found with this user to unblock.")

    # Check if the current user actually initiated the block
    is_blocker = (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == current_db_user.id) or \
                 (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == current_db_user.id)

    if not is_blocker:
        raise HTTPException(status_code=400, detail="You have not blocked this user, or they blocked you.")

    # Unblocking sets the status back to PENDING (or you could delete the record if no prior friendship)
    # If you want to restore previous friendship status, that's more complex (need to store pre-block status)
    # For simplicity, unblocking could mean the relationship is removed, or goes to a neutral state.
    # Let's assume unblocking removes the record, allowing for a fresh start.
    # Or, set to PENDING, with action_user being the one unblocking, effectively "offering" a re-connection.
    # For now, let's just delete the record to signify the end of the block.
    # A more nuanced approach might set it to a neutral state or revert to pre-block status.
    # Let's change this: unblocking will remove the friendship record entirely.
    # This means if they were friends before, they are no longer. They'd have to re-request.
    # This is simpler than trying to restore a previous state.
    
    # Alternative: Set to a neutral state, e.g., if they were friends, they remain friends.
    # If it was PENDING before block, it's gone.
    # This is complex. Let's make unblock simply remove the record for now.
    # If you want to "unblock and revert to previous state", you'd need to store that state.

    # Simpler: Unblocking removes the friendship record. User can re-initiate.
    # db.delete(friendship)

    # More user-friendly: Unblocking sets status to what it might have been before, or neutral.
    # If they were friends, they become friends again. If nothing, then nothing.
    # For now, let's set status to PENDING, with current user as action_user,
    # effectively making them "open" to re-friending. The other user would see nothing changed
    # until a new request is made or accepted.
    # This is still not ideal. The simplest "unblock" is to remove the block status.
    # What was the status before the block? If it was ACCEPTED, should it go back?
    # Let's assume unblocking means the relationship is now "neutral" (no record or a new PENDING if one wants to re-initiate).
    # For this implementation, let's just remove the record.
    
    # Revised: Unblocking sets the status to what it would be if no block existed.
    # If they were friends, they are friends. If it was pending, it's pending from other user.
    # This is too complex without storing pre-block state.
    # Simplest: Unblock removes the record.
    
    # Let's try this: unblocking sets the status to PENDING, with the action_user_id being the one who unblocked.
    # This means the relationship is now open for the other person to accept if they wish, or for the unblocker to send a new request.
    # This is still not perfect.
    # The most straightforward "unblock" is to simply remove the block status.
    # If they were friends before, they are friends again.
    # If the request was pending from the other user, it remains pending from them.
    # If the request was pending from the current user (blocker), it's now unblocked and still pending from them.

    # Let's assume the previous state was "nothing" or "pending from other".
    # Unblocking will effectively delete the friendship record, requiring a new request.
    # This is the cleanest break.
    
    # Final Decision for this iteration: Unblocking removes the friendship record.
    # This forces a re-evaluation of the relationship.
    db.delete(friendship)
    action_message = f"User '{other_user.username}' unblocked. Any previous friendship status is cleared."


    try:
        db.commit()
        # Since the record is deleted, we can't return FriendPublic of the old record.
        # We return a message. The frontend should update its state.
        return JSONResponse(status_code=200, content={"message": action_message})
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")



# Add the router to the main app
app.include_router(friends_router)

dm_router = APIRouter(prefix="/api/dm", tags=["Direct Messaging"])

@dm_router.post("/send", response_model=DirectMessagePublic, status_code=201)
async def send_direct_message(
    dm_data: DirectMessageCreate,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
) -> DirectMessagePublic:
    if current_db_user.id == dm_data.receiver_user_id:
        raise HTTPException(status_code=400, detail="You cannot send a message to yourself.")

    receiver_user = db.query(DBUser).filter(DBUser.id == dm_data.receiver_user_id).first()
    if not receiver_user:
        raise HTTPException(status_code=404, detail="Receiver user not found.")

    # Check friendship status and blocks
    friendship = get_friendship_record(db, current_db_user.id, receiver_user.id) # Uses helper from friends_router

    if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
        # Check for blocks even if not "ACCEPTED" friends, as a block overrides everything
        if friendship: # A record exists, check its status
            if (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == current_db_user.id) or \
               (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == current_db_user.id):
                raise HTTPException(status_code=403, detail="You have blocked this user. Unblock them to send messages.")
            if (friendship.status == FriendshipStatus.BLOCKED_BY_USER1 and friendship.user1_id == receiver_user.id) or \
               (friendship.status == FriendshipStatus.BLOCKED_BY_USER2 and friendship.user2_id == receiver_user.id):
                raise HTTPException(status_code=403, detail="You cannot send a message to this user as they have blocked you.")
        # If no record or not accepted (and not blocked by receiver)
        raise HTTPException(status_code=403, detail="You can only send messages to accepted friends who have not blocked you.")


    new_dm = DirectMessage(
        sender_id=current_db_user.id,
        receiver_id=receiver_user.id,
        content=dm_data.content
        # image_references_json=dm_data.image_references_json # If supporting images
    )
    db.add(new_dm)
    try:
        db.commit()
        db.refresh(new_dm)
        # Eager load sender and receiver for username in response
        db.refresh(new_dm, attribute_names=['sender', 'receiver'])
        
        return DirectMessagePublic(
            id=new_dm.id,
            sender_id=new_dm.sender_id,
            sender_username=new_dm.sender.username,
            receiver_id=new_dm.receiver_id,
            receiver_username=new_dm.receiver.username,
            content=new_dm.content,
            sent_at=new_dm.sent_at,
            read_at=new_dm.read_at
            # image_references_json=new_dm.image_references_json
        )
    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error sending message: {str(e)}")


@dm_router.get("/conversation/{other_user_id_or_username}", response_model=List[DirectMessagePublic])
async def get_dm_conversation(
    other_user_id_or_username: str,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db),
    before_message_id: Optional[int] = None, # For pagination: load messages before this ID
    limit: int = Query(50, ge=1, le=100) # Pagination limit
) -> List[DirectMessagePublic]:
    other_user = None
    try:
        other_user_id_val = int(other_user_id_or_username)
        other_user = db.query(DBUser).filter(DBUser.id == other_user_id_val).first()
    except ValueError:
        other_user = db.query(DBUser).filter(DBUser.username == other_user_id_or_username).first()

    if not other_user:
        raise HTTPException(status_code=404, detail="Other user not found.")
    if other_user.id == current_db_user.id:
        raise HTTPException(status_code=400, detail="Cannot fetch conversation with yourself.")

    # Optional: Check friendship status before allowing to view conversation
    # friendship = get_friendship_record(db, current_db_user.id, other_user.id)
    # if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
    #     raise HTTPException(status_code=403, detail="You can only view conversations with accepted friends.")
    # For now, allow viewing even if unfriended, but sending is restricted.

    query = db.query(DirectMessage).options(
        joinedload(DirectMessage.sender), joinedload(DirectMessage.receiver)
    ).filter(
        or_(
            and_(DirectMessage.sender_id == current_db_user.id, DirectMessage.receiver_id == other_user.id),
            and_(DirectMessage.sender_id == other_user.id, DirectMessage.receiver_id == current_db_user.id)
        )
    ).order_by(DirectMessage.sent_at.desc()) # Get newest first for pagination

    if before_message_id:
        before_message = db.query(DirectMessage).filter(DirectMessage.id == before_message_id).first()
        if before_message:
            query = query.filter(DirectMessage.sent_at < before_message.sent_at)
        else: # Invalid before_message_id, return empty or error
            return [] 
            
    messages_db = query.limit(limit).all()
    
    # Mark messages sent by the other user to current_user as read (if not already)
    # This should ideally be a separate endpoint hit when user opens a conversation
    unread_message_ids = [
        msg.id for msg in messages_db 
        if msg.receiver_id == current_db_user.id and msg.read_at is None
    ]
    if unread_message_ids:
        db.query(DirectMessage).filter(
            DirectMessage.id.in_(unread_message_ids)
        ).update({"read_at": func.now()}, synchronize_session=False)
        db.commit()
        # Re-fetch to get updated read_at times for the response (or update in-memory)
        for msg in messages_db:
            if msg.id in unread_message_ids:
                msg.read_at = datetime.datetime.now(datetime.timezone.utc) # Approximate

    response_list = [
        DirectMessagePublic(
            id=msg.id,
            sender_id=msg.sender_id,
            sender_username=msg.sender.username,
            receiver_id=msg.receiver_id,
            receiver_username=msg.receiver.username,
            content=msg.content,
            sent_at=msg.sent_at,
            read_at=msg.read_at
            # image_references_json=msg.image_references_json
        ) for msg in reversed(messages_db) # Reverse to show oldest first in the fetched page
    ]
    return response_list

# Endpoint to explicitly mark messages as read (better than doing it in GET)
@dm_router.post("/conversation/{other_user_id}/mark_read", status_code=200)
async def mark_dm_conversation_as_read(
    other_user_id: int,
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
):
    # Mark all unread messages received by current_db_user from other_user_id as read
    updated_count = db.query(DirectMessage).filter(
        DirectMessage.sender_id == other_user_id,
        DirectMessage.receiver_id == current_db_user.id,
        DirectMessage.read_at == None
    ).update({"read_at": func.now()}, synchronize_session=False)
    
    db.commit()
    return {"message": f"{updated_count} messages marked as read."}


# Placeholder for listing DM conversations (threads)
# This would typically involve getting the latest message from each unique correspondent.
@dm_router.get("/conversations", response_model=List[Dict[str, Any]]) # Response model needs to be defined
async def list_dm_conversations(
    current_db_user: DBUser = Depends(get_current_db_user),
    db: Session = Depends(get_db)
):
    # This is a complex query to get distinct conversation partners and last message.
    # Using a subquery to get the latest message_id for each conversation pair.
    # SQL might look like:
    # SELECT dm.*, u.username as partner_username FROM direct_messages dm
    # JOIN (
    #   SELECT
    #     CASE WHEN sender_id = :current_user_id THEN receiver_id ELSE sender_id END as partner_id,
    #     MAX(id) as max_id
    #   FROM direct_messages
    #   WHERE sender_id = :current_user_id OR receiver_id = :current_user_id
    #   GROUP BY partner_id
    # ) latest_msg ON dm.id = latest_msg.max_id
    # JOIN users u ON u.id = latest_msg.partner_id
    # ORDER BY dm.sent_at DESC;

    # SQLAlchemy equivalent is more involved. For now, a simplified version:
    # Get all friends, then for each friend, get the last message. This is N+1.
    # A more optimized query is needed for production.

    # Simplified approach: Get all friends, then fetch last message for each.
    friends_response = await get_my_friends(current_db_user, db) # Re-use existing friends list endpoint logic
    
    conversations = []
    for friend in friends_response:
        last_message = db.query(DirectMessage).filter(
            or_(
                and_(DirectMessage.sender_id == current_db_user.id, DirectMessage.receiver_id == friend.id),
                and_(DirectMessage.sender_id == friend.id, DirectMessage.receiver_id == current_db_user.id)
            )
        ).order_by(DirectMessage.sent_at.desc()).first()

        unread_count = db.query(func.count(DirectMessage.id)).filter(
            DirectMessage.sender_id == friend.id, # Messages from friend
            DirectMessage.receiver_id == current_db_user.id, # To me
            DirectMessage.read_at == None
        ).scalar() or 0

        if last_message:
            conversations.append({
                "partner_user_id": friend.id,
                "partner_username": friend.username,
                "last_message_content": last_message.content[:50] + "..." if last_message.content and len(last_message.content) > 50 else last_message.content,
                "last_message_sent_at": last_message.sent_at,
                "last_message_sender_id": last_message.sender_id,
                "unread_count": unread_count
            })
        # else: # Friend with no messages yet, could still be listed
        #    conversations.append({ "partner_user_id": friend.id, "partner_username": friend.username, "unread_count": 0})


    # Sort conversations by last message time, descending
    conversations.sort(key=lambda x: x.get("last_message_sent_at", datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)), reverse=True)
    return conversations


app.include_router(dm_router)