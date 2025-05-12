# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: main.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Main FastAPI application for a multi-user LoLLMs and SafeStore chat service.
# Provides API endpoints for user authentication, discussion management,
# LLM interaction (via lollms-client), RAG (via safe_store),
# file management for RAG, and administrative user management.
# --- Updated: 2025-05-12 ---
# - Fixed SafeStore document deletion (uses doc_id).
# - Added multimodal chat support (image uploads).
# - Minor code refinements.

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
import base64 # For encoding images for lollms-client

# Third-Party Imports
import toml
import yaml
from fastapi import (
    FastAPI, HTTPException, Depends, Request,
    File, UploadFile, Form, APIRouter, Response, Query
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr
from sqlalchemy.orm import Session
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename

# Local Application Imports
from database_setup import (
    User as DBUser,
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY
)
from lollms_client import LollmsClient, MSG_TYPE, LollmsDiscussion as LollmsClientDiscussion

# safe_store is expected to be installed
try:
    import safe_store
    from safe_store import LogLevel as SafeStoreLogLevel # For configuring safe_store log level
except ImportError:
    print("WARNING: safe_store library not found. RAG features will be disabled. Install with: pip install safe_store[all]")
    safe_store = None
    SafeStoreLogLevel = None # Placeholder if safe_store not installed

# --- Application Version ---
APP_VERSION = "1.3.0" # Incremented version (multimodal, bugfix, UI hint)

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
        print(f"CRITICAL: Error parsing config.toml: {e}. Please check the file for syntax errors.")
        config = {}

# Safely get configuration sections with defaults
APP_SETTINGS = config.get("app_settings", {})
APP_DATA_DIR = Path(APP_SETTINGS.get("data_dir", "data")).resolve()
APP_DB_URL = APP_SETTINGS.get(DATABASE_URL_CONFIG_KEY, "sqlite:///./app_main.db")

LOLLMS_CLIENT_DEFAULTS = config.get("lollms_client_defaults", {})
SAFE_STORE_DEFAULTS = config.get("safe_store_defaults", {})
INITIAL_ADMIN_USER_CONFIG = config.get("initial_admin_user", {})
SERVER_CONFIG = config.get("server", {})


# --- Application Data Models (Adapting AppLollmsMessage/Discussion) ---
@dataclass
class AppLollmsMessage:
    """Represents a single message within a discussion for persistence."""
    sender: str
    content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = dataclass_field(default_factory=dict) # To store image info if needed

    def to_dict(self) -> Dict[str, Any]:
        """Converts the message to a dictionary."""
        return {
            'sender': self.sender,
            'content': self.content,
            'id': self.id,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppLollmsMessage':
        """Creates a message from a dictionary."""
        return cls(
            sender=data['sender'],
            content=data['content'],
            id=data.get('id', str(uuid.uuid4())),
            metadata=data.get('metadata', {})
        )

class AppLollmsDiscussion:
    """
    Manages a discussion (a list of AppLollmsMessage) for persistence.
    """
    def __init__(self, lollms_client_instance: LollmsClient, discussion_id: Optional[str] = None, title: Optional[str] = None):
        self.messages: List[AppLollmsMessage] = []
        self.lollms_client: LollmsClient = lollms_client_instance
        self.discussion_id: str = discussion_id or str(uuid.uuid4())
        raw_title = title or f"New Discussion {self.discussion_id[:8]}"
        self.title: str = (raw_title[:250] + "...") if len(raw_title) > 253 else raw_title

    def add_message(self, sender: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> AppLollmsMessage:
        """Adds a message to the discussion."""
        message = AppLollmsMessage(sender=sender, content=content, metadata=metadata or {})
        self.messages.append(message)
        return message

    def edit_message(self, message_id: str, new_content: str) -> bool:
        """Edits an existing message by its ID."""
        for msg in self.messages:
            if msg.id == message_id:
                msg.content = new_content
                return True
        return False

    def delete_message(self, message_id: str) -> bool:
        """Deletes a message by its ID."""
        original_len = len(self.messages)
        self.messages = [msg for msg in self.messages if msg.id != message_id]
        return len(self.messages) < original_len

    def _generate_title_from_messages_if_needed(self) -> None:
        """Generates a title from the first user message if the current title is generic."""
        is_generic_title = self.title.startswith("New Discussion") or \
                           self.title.startswith("Imported") or \
                           self.title.startswith("Discussion ") or \
                           not self.title.strip()

        if is_generic_title and self.messages:
            first_user_message_content = next((m.content for m in self.messages if m.sender.lower() == self.lollms_client.user_name.lower()), None)
            if first_user_message_content:
                new_title_base = first_user_message_content.strip().split('\n')[0]
                max_title_len = 50
                new_title = (new_title_base[:max_title_len-3] + "...") if len(new_title_base) > max_title_len else new_title_base
                if new_title:
                    self.title = new_title

    def to_dict(self) -> Dict[str, Any]:
        """Converts the discussion object to a dictionary representation."""
        self._generate_title_from_messages_if_needed()
        return {
            'discussion_id': self.discussion_id,
            'title': self.title,
            'messages': [message.to_dict() for message in self.messages]
        }

    def save_to_disk(self, file_path: Union[str, Path]) -> None:
        """Saves the discussion to a YAML file."""
        data_to_save = self.to_dict()
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as file:
            yaml.dump(data_to_save, file, sort_keys=False, allow_unicode=True, Dumper=yaml.SafeDumper)

    @classmethod
    def load_from_disk(cls, lollms_client_instance: LollmsClient, file_path: Union[str, Path]) -> Optional['AppLollmsDiscussion']:
        """Loads a discussion from a YAML file."""
        actual_path = Path(file_path)
        if not actual_path.exists():
            print(f"WARNING: Discussion file not found: {actual_path}")
            return None
        try:
            with open(actual_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
        except (yaml.YAMLError, IOError) as e:
            print(f"ERROR: Could not load/parse discussion from {actual_path}: {e}")
            return None

        if not isinstance(data, dict):
            print(f"WARNING: Invalid discussion format in {actual_path}. Attempting migration.")
            disc_id_from_path = actual_path.stem
            discussion = cls(lollms_client_instance, discussion_id=disc_id_from_path, title=f"Imported {disc_id_from_path[:8]}")
            if isinstance(data, list):
                for msg_data in data:
                    if isinstance(msg_data, dict) and 'sender' in msg_data and 'content' in msg_data:
                        discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
            discussion._generate_title_from_messages_if_needed()
            return discussion

        discussion_id = data.get('discussion_id', actual_path.stem)
        title = data.get('title', f"Imported {discussion_id[:8]}")
        discussion = cls(lollms_client_instance, discussion_id=discussion_id, title=title)

        loaded_messages_data = data.get('messages', [])
        if isinstance(loaded_messages_data, list):
            for msg_data in loaded_messages_data:
                if isinstance(msg_data, dict) and 'sender' in msg_data and 'content' in msg_data:
                    discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
                else:
                    print(f"WARNING: Skipping malformed message data in {actual_path}: {msg_data}")

        if not discussion.title or discussion.title.startswith("Imported ") or discussion.title.startswith("New Discussion "):
            discussion._generate_title_from_messages_if_needed()
        return discussion

    def prepare_query_for_llm(self, current_prompt_text: str, images_base64: Optional[List[str]] = None, max_total_tokens: Optional[int] = None) -> Union[str, List[Dict[str,Any]]]:
        """
        Prepares the full prompt (history + current query + images if chat format) for the LLM.
        Returns a string for instruction models or a list of dicts for chat models.
        """
        lc = self.lollms_client
        if max_total_tokens is None:
            max_total_tokens = getattr(lc, 'ctx_size', LOLLMS_CLIENT_DEFAULTS.get('ctx_size', 4096))

        client_discussion = LollmsClientDiscussion(lc)
        for app_msg in self.messages:
            # Basic conversion, may need adjustment if messages contain image metadata
            client_discussion.add_message(sender=app_msg.sender, content=app_msg.content)

        # Estimate current turn tokens (might be inaccurate without exact client tokenization)
        # Account for prompt and potential image placeholders/cost if possible
        current_turn_base_cost = len(current_prompt_text) // 3
        if images_base64:
            # Very rough estimate for image tokens (highly model dependent)
            # OpenAI uses a formula, others might be simpler or complex. Assume ~100 tokens per image?
            current_turn_base_cost += len(images_base64) * 100
        
        tokens_for_history = max_total_tokens - current_turn_base_cost - 100 # Subtract buffer
        if tokens_for_history < 0: tokens_for_history = 0

        # Use lollms-client's formatting capabilities if possible
        # The format_discussion method in lollms-client v0.10 might only return string
        # Need to adapt based on whether the binding expects string or message list
        
        # binding_name = lc.binding.binding_name if lc.binding else "unknown"
        # is_chat_model_binding = "openai" in binding_name.lower() or "ollama" in binding_name.lower() # Common chat bindings

        if images_base64:
            # Prepare messages list for chat completion format
            history_messages = client_discussion.get_messages_for_model(max_allowed_tokens=tokens_for_history) # Assuming this method exists & works

            # Construct the final user message, including images if provided
            user_message_content: List[Dict[str, Any]] = [{"type": "text", "text": current_prompt_text}]
            if images_base64:
                for img_b64 in images_base64:
                    # Assuming base64 format is suitable for the binding (OpenAI/Ollama use this)
                    user_message_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"} # Assuming JPEG, adjust if needed
                    })
            
            final_messages = history_messages + [{"role": "user", "content": user_message_content}]
            return final_messages
        else:
            # Prepare a single string prompt for instruction models
            history_text = client_discussion.format_discussion(max_allowed_tokens=tokens_for_history)
            user_prefix = f"{lc.separator_template}{lc.user_name}"
            ai_prefix = f"\n{lc.separator_template}{lc.ai_name}\n"
            full_prompt = f"{history_text}{user_prefix}\n{current_prompt_text}{ai_prefix}"
            return full_prompt


# --- Pydantic Models for API ---
class UserAuthDetails(BaseModel):
    """User details returned after successful authentication."""
    username: str
    is_admin: bool
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    lollms_client_ai_name: Optional[str] = None

class UserCreateAdmin(BaseModel):
    """Data model for creating a new user via admin panel."""
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8)
    is_admin: bool = False
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None

class UserPasswordResetAdmin(BaseModel):
    """Data model for resetting a user's password via admin panel."""
    new_password: constr(min_length=8)

class UserPublic(BaseModel):
    """Public representation of a user."""
    id: int
    username: str
    is_admin: bool
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    model_config = {"from_attributes": True}

class DiscussionInfo(BaseModel):
    """Basic information about a discussion."""
    id: str
    title: str

class DiscussionTitleUpdate(BaseModel):
    """Data model for updating a discussion's title."""
    title: constr(min_length=1, max_length=255)

class MessageOutput(BaseModel):
    """Representation of a message for API output."""
    id: str
    sender: str
    content: str
    metadata: Dict[str, Any] = {} # Include metadata in output
    model_config = {"from_attributes": True}

class MessageContentUpdate(BaseModel):
    """Data model for updating a message's content."""
    content: str

class SafeStoreDocumentInfo(BaseModel):
    """Information about a document in SafeStore."""
    filename: str

class DiscussionExportRequest(BaseModel):
    """Request model for exporting specific discussions."""
    discussion_ids: Optional[List[str]] = None

class ExportData(BaseModel):
    """Data model for exported user data."""
    exported_by_user: str
    export_timestamp: str
    application_version: str
    user_settings_at_export: Dict[str, Optional[str]]
    safestore_info: Dict[str, Any]
    discussions: List[Dict[str, Any]]


# --- Global User Session Management ---
user_sessions: Dict[str, Dict[str, Any]] = {}


# --- FastAPI Application Setup ---
app = FastAPI(
    title="Simplified LoLLMs Chat API",
    description="API for a multi-user LoLLMs and SafeStore chat application with RAG and file management.",
    version=APP_VERSION,
)
security = HTTPBasic()

# --- FastAPI Event Handlers ---
@app.on_event("startup")
async def on_startup() -> None:
    """Handles application startup tasks like directory and database initialization."""
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
            default_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
            default_vectorizer = SAFE_STORE_DEFAULTS.get("global_default_vectorizer")

            new_admin = DBUser(
                username=admin_username,
                hashed_password=hashed_admin_pass,
                is_admin=True,
                lollms_model_name=default_model,
                safe_store_vectorizer=default_vectorizer
            )
            db.add(new_admin)
            db.commit()
            print(f"INFO: Initial admin user '{admin_username}' created successfully.")
        else:
            print(f"INFO: Initial admin user '{admin_username}' already exists.")
    except Exception as e:
        print(f"ERROR: Failed during initial admin user setup: {e}")
        traceback.print_exc()
    finally:
        if db: db.close()


# --- User-specific Path Helpers ---
def get_user_data_root(username: str) -> Path:
    """Returns the root data directory for a given user."""
    if ".." in username or "/" in username or "\\" in username or not username.isalnum() and "_" not in username and "-" not in username:
        print(f"WARNING: Attempt to access user data root with invalid username: '{username}'")
        raise HTTPException(status_code=400, detail="Invalid username format for path.")
    path = APP_DATA_DIR / username
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_discussion_path(username: str) -> Path:
    """Returns the discussions directory for a given user."""
    path = get_user_data_root(username) / "discussions"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_safestore_documents_path(username: str) -> Path:
    """Returns the SafeStore documents directory for a given user."""
    path = get_user_data_root(username) / "safestore_documents"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_user_temp_uploads_path(username: str) -> Path:
    """Returns the temporary uploads directory for a given user."""
    path = get_user_data_root(username) / "temp_uploads"
    path.mkdir(parents=True, exist_ok=True)
    # Consider adding cleanup mechanism for this directory
    return path


# --- Authentication Dependencies ---
def get_current_db_user(credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)) -> DBUser:
    """Authenticates a user based on HTTP Basic credentials and database lookup."""
    user = db.query(DBUser).filter(DBUser.username == credentials.username).first()
    if not user or not user.verify_password(credentials.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password", headers={"WWW-Authenticate": "Basic"})
    return user

def get_current_active_user(db_user: DBUser = Depends(get_current_db_user)) -> UserAuthDetails:
    """
    Retrieves active user details and initializes their session if not already present.
    This function is crucial for setting up user-specific LollmsClient and SafeStore instances.
    """
    username = db_user.username
    if username not in user_sessions:
        print(f"INFO: Initializing session state for user: {username}")

        initial_lollms_model = db_user.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
        initial_vectorizer = db_user.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer")

        user_sessions[username] = {
            "lollms_client": None,
            "safe_store_instance": None,
            "discussions": {},
            "discussion_titles": {},
            "active_vectorizer": initial_vectorizer,
            "lollms_model_name": initial_lollms_model,
        }

    lc = get_user_lollms_client(username)
    ai_name_for_user = getattr(lc, 'ai_name', LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))

    if not user_sessions[username].get("discussions"):
         _load_user_discussions(username)

    return UserAuthDetails(
        username=username,
        is_admin=db_user.is_admin,
        lollms_model_name=user_sessions[username]["lollms_model_name"],
        safe_store_vectorizer=user_sessions[username]["active_vectorizer"],
        lollms_client_ai_name=ai_name_for_user
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    """Ensures the current user has administrator privileges."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required.")
    return current_user


# --- Helper Functions for User-Specific Services ---
def get_user_lollms_client(username: str) -> LollmsClient:
    """Retrieves or initializes the LollmsClient for a given user."""
    session = user_sessions.get(username)
    if not session:
        print(f"ERROR: User session for {username} not found when trying to get LollmsClient.")
        raise HTTPException(status_code=500, detail="User session not found for LollmsClient.")

    if session.get("lollms_client") is None:
        model_name = session["lollms_model_name"]
        binding_name = LOLLMS_CLIENT_DEFAULTS.get("binding_name", "lollms")
        host_address = LOLLMS_CLIENT_DEFAULTS.get("host_address")
        ctx_size = LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096)
        service_key_env_name = LOLLMS_CLIENT_DEFAULTS.get("service_key_env_var")
        service_key = os.getenv(service_key_env_name) if service_key_env_name else None
        user_name_conf = LOLLMS_CLIENT_DEFAULTS.get("user_name", "user")
        ai_name_conf = LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant")
        temperature_conf = LOLLMS_CLIENT_DEFAULTS.get("temperature")
        top_k_conf = LOLLMS_CLIENT_DEFAULTS.get("top_k")
        top_p_conf = LOLLMS_CLIENT_DEFAULTS.get("top_p")

        try:
            print(f"INFO: Initializing LollmsClient for {username} (Binding: {binding_name}, Model: {model_name or 'Default'}, Host: {host_address or 'Default'})")
            client_params = {
                "binding_name": binding_name, "model_name": model_name,
                "host_address": host_address, "ctx_size": ctx_size,
                "service_key": service_key, "user_name": user_name_conf, "ai_name": ai_name_conf
            }
            if temperature_conf is not None: client_params["temperature"] = temperature_conf
            if top_k_conf is not None: client_params["top_k"] = top_k_conf
            if top_p_conf is not None: client_params["top_p"] = top_p_conf

            lc = LollmsClient(**client_params)
            session["lollms_client"] = lc
        except Exception as e:
            print(f"ERROR: Failed to initialize LollmsClient for {username}: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize LLM Client: {str(e)}")
    return cast(LollmsClient, session["lollms_client"])

def get_user_safe_store(username: str) -> safe_store.SafeStore:
    """Retrieves or initializes the SafeStore instance for a given user."""
    if safe_store is None:
         raise HTTPException(status_code=501, detail="SafeStore library not installed or failed to import. RAG is disabled.")
    session = user_sessions.get(username)
    if not session:
        print(f"ERROR: User session for {username} not found when trying to get SafeStore.")
        raise HTTPException(status_code=500, detail="User session not found for SafeStore.")

    if session.get("safe_store_instance") is None:
        user_data_path = get_user_data_root(username)
        ss_db_path = user_data_path / "vector_store.db"
        encryption_key = SAFE_STORE_DEFAULTS.get("encryption_key")

        log_level_str = SAFE_STORE_DEFAULTS.get("log_level", "INFO").upper()
        ss_log_level = getattr(SafeStoreLogLevel, log_level_str, SafeStoreLogLevel.INFO) if SafeStoreLogLevel else None

        try:
            print(f"INFO: Initializing SafeStore for {username} at {ss_db_path}")
            ss_params = {"db_path": ss_db_path, "encryption_key": encryption_key}
            if ss_log_level is not None: ss_params["log_level"] = ss_log_level

            ss_instance = safe_store.SafeStore(**ss_params)
            session["safe_store_instance"] = ss_instance
        except safe_store.ConfigurationError as e:
             print(f"ERROR: Configuration error initializing SafeStore for {username}: {e}")
             raise HTTPException(status_code=500, detail=f"SafeStore configuration error: {str(e)}. Check dependencies (e.g., safe_store[encryption]).")
        except Exception as e:
            print(f"ERROR: Failed to initialize SafeStore for {username}: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize SafeStore: {str(e)}")
    return cast(safe_store.SafeStore, session["safe_store_instance"])


# --- Discussion Management Helper Functions ---
def _load_user_discussions(username: str) -> None:
    """Loads all discussions for a user from disk into their session."""
    try:
        lc = get_user_lollms_client(username)
    except HTTPException as e:
        print(f"ERROR: Cannot load discussions for {username}; LollmsClient unavailable: {e.detail}")
        if username in user_sessions:
            user_sessions[username]["discussions"] = {}
            user_sessions[username]["discussion_titles"] = {}
        return

    discussion_dir = get_user_discussion_path(username)
    session = user_sessions[username] # Get session after ensuring client is ready
    session["discussions"] = {}
    session["discussion_titles"] = {}
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
        else:
            print(f"WARNING: Failed to load discussion from {file_path} for user {username}.")
    print(f"INFO: Loaded {loaded_count} discussions for user {username}.")

def get_user_discussion(username: str, discussion_id: str, create_if_missing: bool = False) -> Optional[AppLollmsDiscussion]:
    """Retrieves a specific discussion for a user, optionally creating it if missing."""
    session = user_sessions.get(username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found.")

    discussion_obj = session["discussions"].get(discussion_id)
    if discussion_obj: return discussion_obj

    safe_discussion_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_discussion_filename.endswith(".yaml") or safe_discussion_filename == ".yaml":
        raise HTTPException(status_code=400, detail="Invalid discussion ID format.")

    file_path = get_user_discussion_path(username) / safe_discussion_filename
    lc = get_user_lollms_client(username)

    if file_path.exists():
        disk_obj = AppLollmsDiscussion.load_from_disk(lc, file_path)
        if disk_obj:
            disk_obj.discussion_id = discussion_id
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
    """Saves a user's discussion object to disk."""
    safe_discussion_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_discussion_filename.endswith(".yaml") or safe_discussion_filename == ".yaml":
        raise HTTPException(status_code=400, detail="Invalid discussion ID format for saving.")

    file_path = get_user_discussion_path(username) / safe_discussion_filename
    try:
        discussion_obj.save_to_disk(file_path)
        if username in user_sessions:
            user_sessions[username]["discussion_titles"][discussion_id] = discussion_obj.title
    except Exception as e:
        print(f"ERROR: Failed to save discussion {discussion_id} for user {username} to {file_path}: {e}")
        traceback.print_exc()


# --- Root and Static File Endpoints ---
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index_html(request: Request) -> FileResponse:
    """Serves the main index.html page."""
    index_path = Path("index.html").resolve()
    if not index_path.is_file(): raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(index_path)

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def serve_admin_panel_page(admin_user: UserAuthDetails = Depends(get_current_admin_user)) -> FileResponse:
    """Serves the admin.html page (requires admin authentication)."""
    admin_html_path = Path("admin.html").resolve()
    if not admin_html_path.is_file(): raise HTTPException(status_code=404, detail="admin.html not found.")
    return FileResponse(admin_html_path)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """Serves the favicon.ico."""
    favicon_path = Path("favicon.ico").resolve()
    return FileResponse(favicon_path, media_type="image/x-icon") if favicon_path.is_file() else Response(status_code=204)

@app.get("/logo.png", include_in_schema=False)
async def logo() -> Response:
    """Serves the logo.png."""
    logo_path = Path("logo.png").resolve()
    return FileResponse(logo_path, media_type="image/png") if logo_path.is_file() else Response(status_code=404)

try:
    locales_path = Path("locales").resolve()
    if locales_path.is_dir():
        app.mount("/locales", StaticFiles(directory=locales_path, html=False), name="locales")
    else:
        print("WARNING: 'locales' directory not found. Localization files will not be served.")
except Exception as e:
    print(f"ERROR: Failed to mount locales directory: {e}")


# --- Authentication API ---
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
@auth_router.get("/me", response_model=UserAuthDetails)
async def get_my_details(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    """Returns details of the currently authenticated user."""
    return current_user
app.include_router(auth_router)


# --- Discussion API ---
discussion_router = APIRouter(prefix="/api/discussions", tags=["Discussions"])

@discussion_router.get("", response_model=List[DiscussionInfo])
async def list_all_discussions(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[DiscussionInfo]:
    """Lists all discussions for the authenticated user."""
    username = current_user.username
    if username not in user_sessions or not user_sessions[username].get("discussion_titles"):
        _load_user_discussions(username) # Ensure discussions are loaded
    titles_map = user_sessions[username].get("discussion_titles", {})
    return [DiscussionInfo(id=disc_id, title=title) for disc_id, title in titles_map.items()]

@discussion_router.post("", response_model=DiscussionInfo, status_code=201)
async def create_new_discussion(current_user: UserAuthDetails = Depends(get_current_active_user)) -> DiscussionInfo:
    """Creates a new discussion for the authenticated user."""
    username = current_user.username
    discussion_id = str(uuid.uuid4())
    discussion_obj = get_user_discussion(username, discussion_id, create_if_missing=True)
    if not discussion_obj:
        raise HTTPException(status_code=500, detail="Failed to create or retrieve new discussion object.")
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title)

@discussion_router.get("/{discussion_id}", response_model=List[MessageOutput])
async def get_messages_for_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[MessageOutput]:
    """Retrieves all messages for a specific discussion."""
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    return [MessageOutput.model_validate(msg) for msg in discussion_obj.messages]

@discussion_router.put("/{discussion_id}/title", response_model=DiscussionInfo)
async def update_discussion_title(discussion_id: str, title_update: DiscussionTitleUpdate, current_user: UserAuthDetails = Depends(get_current_active_user)) -> DiscussionInfo:
    """Updates the title of a specific discussion."""
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")
    discussion_obj.title = title_update.title
    save_user_discussion(username, discussion_id, discussion_obj)
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title)

@discussion_router.delete("/{discussion_id}", status_code=200)
async def delete_specific_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)) -> Dict[str, str]:
    """Deletes a specific discussion and its associated file."""
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
            if file_path.exists(): raise HTTPException(status_code=500, detail=f"Failed to delete discussion file: {e}")
    return {"message": f"Discussion '{discussion_id}' deleted successfully."}

@discussion_router.post("/{discussion_id}/chat")
async def chat_in_existing_discussion(
    discussion_id: str,
    prompt: str = Form(...),
    use_rag: bool = Form(False),
    files: Optional[List[UploadFile]] = File(None), # Accept optional image files
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> StreamingResponse:
    """Handles chat interactions within a discussion, supporting RAG, images, and streaming responses."""
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    lc = get_user_lollms_client(username)
    image_paths: List[str] = []
    image_metadata: Dict[str, Any] = {"image_count": 0, "filenames": []}
    images_base64: List[str] = [] # For passing to lollms-client

    if files:
        temp_upload_dir = get_user_temp_uploads_path(username)
        for file in files:
            if file.content_type and "image" in file.content_type:
                s_filename = secure_filename(file.filename or f"upload_{uuid.uuid4().hex[:8]}")
                temp_file_path = temp_upload_dir / s_filename
                try:
                    with open(temp_file_path, "wb") as buffer:
                        shutil.copyfileobj(file.file, buffer)
                    image_paths.append(str(temp_file_path))
                    image_metadata["filenames"].append(s_filename)
                    # Encode image to base64 for lollms-client
                    with open(temp_file_path, "rb") as img_file:
                        images_base64.append(base64.b64encode(img_file.read()).decode('utf-8'))

                except Exception as e:
                    print(f"ERROR: Failed to process uploaded image {s_filename}: {e}")
                finally:
                    file.file.close()
        image_metadata["image_count"] = len(image_paths)

    # Add user message to discussion FIRST (including image info if any)
    discussion_obj.add_message(sender=lc.user_name, content=prompt, metadata=image_metadata if image_paths else None)

    final_prompt_for_llm = prompt
    if use_rag and safe_store:
        active_vectorizer = user_sessions[username].get("active_vectorizer")
        if active_vectorizer:
            ss = get_user_safe_store(username)
            try:
                with ss: rag_results = ss.query(prompt, vectorizer_name=active_vectorizer, top_k=3)
                if rag_results:
                    context_str = "\n\nRelevant context from documents:\n"
                    max_rag_len, current_rag_len, sources = 2000, 0, set()
                    for i, res in enumerate(rag_results):
                        chunk_text = res.get('chunk_text','')
                        if current_rag_len + len(chunk_text) > max_rag_len and i > 0:
                            context_str += f"... (truncated {len(rag_results) - i} more results)\n"; break
                        context_str += f"{i+1}. From '{Path(res.get('file_path','?')).name}': {chunk_text}\n"
                        current_rag_len += len(chunk_text); sources.add(Path(res.get('file_path','?')).name)

                    final_prompt_for_llm = (f"User question: {prompt}\n\n"
                                           f"Use the following context from ({', '.join(sorted(list(sources)))}) to answer if relevant:\n{context_str.strip()}")
                    print(f"INFO: RAG context added for user {username}, discussion {discussion_id}.")
            except Exception as e: print(f"ERROR: RAG query failed for {username}: {e}")
        else: print(f"WARNING: RAG requested by {username} but no active vectorizer.")
    elif use_rag and not safe_store: print(f"WARNING: RAG requested by {username} but safe_store is not available.")

    main_loop = asyncio.get_event_loop()
    stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    shared_state = {"accumulated_ai_response": "", "generation_error": None}

    async def stream_generator() -> AsyncGenerator[str, None]:
        def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict[str, Any]] = None) -> bool:
            if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                shared_state["accumulated_ai_response"] += chunk
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "chunk", "content": chunk}) + "\n")
            elif msg_type == MSG_TYPE.MSG_TYPE_EXCEPTION or msg_type == MSG_TYPE.MSG_TYPE_ERROR:
                err_content = f"LLM Error: {str(chunk)}"
                shared_state["generation_error"] = err_content
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_content}) + "\n")
                return False
            elif msg_type == MSG_TYPE.MSG_TYPE_FINISHED_MESSAGE:
                return False
            return True

        generation_thread: Optional[threading.Thread] = None
        try:
            # Prepare prompt/messages for lollms-client
            prepared_input = discussion_obj.prepare_query_for_llm(
                current_prompt_text=final_prompt_for_llm,
                images_base64=images_base64 if images_base64 else None
            )

            def blocking_call():
                try:
                    # generate_text handles both string and message list inputs
                    lc.generate_text(
                        prompt=prepared_input, # Pass either string or message list
                        stream=True,
                        streaming_callback=llm_callback,
                        # images parameter is only used if prompt is a string;
                        # for message list format, images are embedded in the content.
                        # lollms-client should handle this internally based on prompt type.
                    )
                except Exception as e_gen:
                    err_msg = f"LLM generation failed: {str(e_gen)}"
                    # Check if error indicates image incompatibility
                    if "doesn't support image input" in str(e_gen).lower() or "multimodal" in str(e_gen).lower():
                         err_msg += " (Model may not support images)"
                    shared_state["generation_error"] = err_msg
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
                finally:
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None) # Signal end of stream

            generation_thread = threading.Thread(target=blocking_call, daemon=True)
            generation_thread.start()

            while True:
                item = await stream_queue.get()
                if item is None: stream_queue.task_done(); break
                yield item
                stream_queue.task_done()

            if generation_thread: generation_thread.join(timeout=5)

            # Add final AI response or error to discussion history
            if shared_state["accumulated_ai_response"] and not shared_state["generation_error"]:
                discussion_obj.add_message(sender=lc.ai_name, content=shared_state["accumulated_ai_response"])
            elif shared_state["generation_error"]:
                 discussion_obj.add_message(sender="system", content=shared_state["generation_error"])

            save_user_discussion(username, discussion_id, discussion_obj) # Save AFTER adding AI response/error

        except Exception as e_outer:
            error_msg = f"Chat stream error: {str(e_outer)}"
            traceback.print_exc()
            try:
                discussion_obj.add_message(sender="system", content=error_msg)
                save_user_discussion(username, discussion_id, discussion_obj)
            except Exception as save_err:
                print(f"ERROR: Failed to save discussion after outer stream error: {save_err}")
            yield json.dumps({"type": "error", "content": error_msg}) + "\n"
        finally:
            # Clean up temporary image files
            for img_path_str in image_paths:
                try: Path(img_path_str).unlink(missing_ok=True)
                except Exception as clean_err: print(f"ERROR: Failed to delete temp image {img_path_str}: {clean_err}")

            if generation_thread and generation_thread.is_alive():
                print(f"WARNING: LLM gen thread for {username} still alive after stream end.")

    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")


@discussion_router.put("/{discussion_id}/messages/{message_id}", response_model=MessageOutput)
async def update_discussion_message(discussion_id: str, message_id: str, payload: MessageContentUpdate, current_user: UserAuthDetails = Depends(get_current_active_user)) -> MessageOutput:
    """Updates the content of a specific message within a discussion."""
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj or not discussion_obj.edit_message(message_id, payload.content):
        raise HTTPException(status_code=404, detail="Message or discussion not found.")
    save_user_discussion(username, discussion_id, discussion_obj)
    updated_msg = next((m for m in discussion_obj.messages if m.id == message_id), None)
    if not updated_msg: raise HTTPException(status_code=500, detail="Error retrieving updated message.")
    return MessageOutput.model_validate(updated_msg)

@discussion_router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
async def delete_discussion_message(discussion_id: str, message_id: str, current_user: UserAuthDetails = Depends(get_current_active_user)) -> Dict[str, str]:
    """Deletes a specific message from a discussion."""
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj or not discussion_obj.delete_message(message_id):
        raise HTTPException(status_code=404, detail="Message or discussion not found.")
    save_user_discussion(username, discussion_id, discussion_obj)
    return {"message": "Message deleted successfully."}

@discussion_router.post("/export", response_model=ExportData)
async def export_user_data(
    export_request: DiscussionExportRequest,
    current_user: UserAuthDetails = Depends(get_current_active_user)
) -> ExportData:
    """Exports user data, including selected or all discussions and SafeStore info."""
    username = current_user.username
    user_settings = {"lollms_model_name": user_sessions[username]["lollms_model_name"],
                     "safe_store_vectorizer": user_sessions[username]["active_vectorizer"]}
    safestore_info = {"vectorizers": [], "documents_info": [], "error": None}
    if safe_store:
        try:
            ss = get_user_safe_store(username)
            with ss:
                safestore_info["vectorizers"] = ss.list_vectorization_methods()
                docs_in_store = ss.list_documents()
                safestore_info["documents_info"] = [{"filename": Path(d["file_path"]).name, "metadata": d.get("metadata")}
                                                    for d in docs_in_store if "file_path" in d]
        except Exception as e: safestore_info["error"] = str(e)
    else: safestore_info["error"] = "SafeStore library not available."

    if not user_sessions[username].get("discussions"):
         _load_user_discussions(username)

    all_user_discussions_map = user_sessions[username].get("discussions", {})

    if export_request.discussion_ids is not None: # Check for None, empty list means export none explicitly selected
        discussions_to_export_values = [
            all_user_discussions_map[disc_id]
            for disc_id in export_request.discussion_ids
            if disc_id in all_user_discussions_map
        ]
    else: # Export all if discussion_ids is None
        discussions_to_export_values = list(all_user_discussions_map.values())

    discussions_data = [d.to_dict() for d in discussions_to_export_values]

    return ExportData(
        exported_by_user=username,
        export_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        application_version=APP_VERSION,
        user_settings_at_export=user_settings,
        safestore_info=safestore_info,
        discussions=discussions_data
    )
app.include_router(discussion_router)


# --- LoLLMs Configuration API ---
lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])
@lollms_config_router.get("/lollms-models", response_model=List[Dict[str, str]])
async def get_available_lollms_models(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[Dict[str, str]]:
    """Lists available LoLLMs models based on client bindings and user settings."""
    lc = get_user_lollms_client(current_user.username)
    models_set: set[str] = set()
    try:
        binding_models = lc.listModels()
        if isinstance(binding_models, list):
            for item in binding_models:
                if isinstance(item, str): models_set.add(item)
                elif isinstance(item, dict):
                    name = item.get('name', item.get('id', item.get('model_name')))
                    if name: models_set.add(name)
    except Exception as e: print(f"WARNING: Could not list models from LollmsClient: {e}")

    user_model = user_sessions[current_user.username].get("lollms_model_name")
    if user_model: models_set.add(user_model)
    global_default_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
    if global_default_model: models_set.add(global_default_model)

    models_set.discard('')
    if not models_set and lc.binding is not None and "openai" in lc.binding.binding_name.lower():
        models_set.update(["gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])

    models = [{"name": name} for name in sorted(list(models_set))] if models_set else [{"name": "No models found"}]
    return models

@lollms_config_router.post("/lollms-model")
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Sets the default LoLLMs model for the authenticated user."""
    username = current_user.username
    user_sessions[username]["lollms_model_name"] = model_name
    user_sessions[username]["lollms_client"] = None # Force reinitialization on next use

    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user_record:
        db_user_record.lollms_model_name = model_name
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    else: raise HTTPException(status_code=404, detail="User not found for model update.")
    return {"message": f"Default LoLLMs model set to '{model_name}'. Client will re-initialize."}
app.include_router(lollms_config_router)


# --- SafeStore (RAG) API ---
store_router = APIRouter(prefix="/api/store", tags=["SafeStore RAG & File Management"])
@store_router.get("/vectorizers", response_model=List[Dict[str,str]])
async def list_safe_store_vectorizers(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[Dict[str,str]]:
    """Lists available SafeStore vectorization methods (both potential and already used)."""
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    ss = get_user_safe_store(current_user.username)
    try:
        with ss:
            methods_in_db = ss.list_vectorization_methods()
            possible_names = ss.list_possible_vectorizer_names()

            formatted_vectorizers = []
            existing_method_names = set()

            for method_info in methods_in_db:
                name = method_info.get('method_name')
                if name:
                    formatted_vectorizers.append({"name": name, "method_name": f"{name} (dim: {method_info.get('vector_dim', 'N/A')})"})
                    existing_method_names.add(name)

            for possible_name in possible_names:
                if possible_name not in existing_method_names:
                    display_text = possible_name
                    if possible_name.startswith("tfidf:"):
                        display_text = f"{possible_name} (TF-IDF, auto-fit)"
                    elif possible_name.startswith("st:"):
                        display_text = f"{possible_name} (Sentence Transformer)"

                    formatted_vectorizers.append({"name": possible_name, "method_name": display_text})

            final_list = []
            seen_names = set()
            for fv in formatted_vectorizers:
                if fv["name"] not in seen_names:
                    final_list.append(fv)
                    seen_names.add(fv["name"])

            final_list.sort(key=lambda x: x["name"])
            return final_list

    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing vectorizers: {e}")


@store_router.get("/active-vectorizer", response_model=Dict[str, Optional[str]])
async def get_session_active_vectorizer(current_user: UserAuthDetails = Depends(get_current_active_user)) -> Dict[str, Optional[str]]:
    """Gets the currently active RAG vectorizer for the user's session."""
    return {"active_vectorizer": user_sessions[current_user.username].get("active_vectorizer")}

@store_router.post("/active-vectorizer")
async def set_session_active_vectorizer(vectorizer_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    """Sets the active RAG vectorizer for the user's session and persists it."""
    username = current_user.username
    user_sessions[username]["active_vectorizer"] = vectorizer_name
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user_record:
        db_user_record.safe_store_vectorizer = vectorizer_name
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    else: raise HTTPException(status_code=404, detail="User not found.")
    return {"message": f"Active RAG vectorizer set to '{vectorizer_name}'."}

@store_router.post("/upload-files")
async def upload_rag_documents(files: List[UploadFile] = File(...), vectorizer_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user)) -> JSONResponse:
    """Uploads documents to SafeStore for RAG, using the specified vectorizer."""
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    username = current_user.username
    ss = get_user_safe_store(username)
    user_docs_path = get_user_safestore_documents_path(username)
    processed, errors_list = [], []

    try:
        with ss:
            all_vectorizers = {m['method_name'] for m in ss.list_vectorization_methods()} | set(ss.list_possible_vectorizer_names())
        if vectorizer_name not in all_vectorizers and not vectorizer_name.startswith("st:") and not vectorizer_name.startswith("tfidf:"):
             raise HTTPException(status_code=400, detail=f"Vectorizer '{vectorizer_name}' not found or invalid. Use 'st:model_name' or 'tfidf:custom_name'.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error checking vectorizer: {e}")

    for file_upload in files:
        s_filename = secure_filename(file_upload.filename or f"upload_{uuid.uuid4().hex[:8]}")
        target_file_path = user_docs_path / s_filename
        try:
            with open(target_file_path, "wb") as buffer: shutil.copyfileobj(file_upload.file, buffer)
            with ss: ss.add_document(str(target_file_path), vectorizer_name=vectorizer_name)
            processed.append(s_filename)
        except Exception as e:
            errors_list.append({"filename": s_filename, "error": str(e)})
            target_file_path.unlink(missing_ok=True)
        finally: file_upload.file.close()

    if errors_list and processed: status_code, msg = 207, "Some files processed with errors."
    elif errors_list: status_code, msg = 400, "Failed to process uploaded files."
    else: status_code, msg = 200, "All files uploaded and processed successfully."
    return JSONResponse(status_code=status_code, content={"message": msg, "processed_files": processed, "errors": errors_list})

@store_router.get("/files", response_model=List[SafeStoreDocumentInfo])
async def list_rag_documents(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[SafeStoreDocumentInfo]:
    """Lists documents managed by SafeStore for the user."""
    if not safe_store: return []
    username = current_user.username
    user_docs_path_resolved = get_user_safestore_documents_path(username).resolve()
    ss = get_user_safe_store(username)
    managed_docs = []
    try:
        with ss: stored_meta = ss.list_documents()
        for doc_meta in stored_meta:
            original_path_str = doc_meta.get("file_path")
            if original_path_str:
                try:
                    if Path(original_path_str).resolve().parent == user_docs_path_resolved:
                        managed_docs.append(SafeStoreDocumentInfo(filename=Path(original_path_str).name))
                except Exception: pass
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing RAG docs: {e}")
    return managed_docs

@store_router.delete("/files/{filename}")
async def delete_rag_document(filename: str, current_user: UserAuthDetails = Depends(get_current_active_user)) -> Dict[str, str]:
    """Deletes a document from SafeStore and the user's document storage."""
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    username = current_user.username
    s_filename = secure_filename(filename)
    if not s_filename or s_filename != filename: raise HTTPException(status_code=400, detail="Invalid filename.")

    file_to_delete_path = get_user_safestore_documents_path(username) / s_filename
    if not file_to_delete_path.is_file(): raise HTTPException(status_code=404, detail=f"Document '{s_filename}' not found.")

    ss = get_user_safe_store(username)
    try:
        doc_id_to_delete = None
        with ss:
            all_docs = ss.list_documents()
            for doc in all_docs:
                # Compare resolved paths for robustness
                if doc.get("file_path") and Path(doc["file_path"]).resolve() == file_to_delete_path.resolve():
                    doc_id_to_delete = doc.get("doc_id")
                    break

        if doc_id_to_delete is None:
            raise HTTPException(status_code=404, detail=f"Document '{s_filename}' found on disk but not in SafeStore DB.")

        with ss:
            # Assuming safe_store has delete_document(doc_id=...)
            # If safe_store v1.6+ has delete_document_by_path, revert to that.
            ss.delete_document(doc_id=doc_id_to_delete)
        
        file_to_delete_path.unlink()
        return {"message": f"Document '{s_filename}' deleted successfully."}
    except safe_store.SafeStoreError as e:
        # Handle SafeStore specific errors, e.g., if delete_document fails
        raise HTTPException(status_code=500, detail=f"SafeStore error deleting '{s_filename}': {e}")
    except OSError as e:
        # Handle file system deletion errors
        raise HTTPException(status_code=500, detail=f"Error deleting file '{s_filename}' from disk: {e}")
    except Exception as e:
        # Catch-all for other unexpected errors
        raise HTTPException(status_code=500, detail=f"Could not delete '{s_filename}': {e}")
app.include_router(store_router)


# --- Admin API ---
admin_router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(get_current_admin_user)])
@admin_router.get("/users", response_model=List[UserPublic])
async def admin_get_all_users(db: Session = Depends(get_db)) -> List[DBUser]:
    """(Admin) Retrieves a list of all users."""
    return db.query(DBUser).all()

@admin_router.post("/users", response_model=UserPublic, status_code=201)
async def admin_add_new_user(user_data: UserCreateAdmin, db: Session = Depends(get_db)) -> DBUser:
    """(Admin) Adds a new user to the system."""
    if db.query(DBUser).filter(DBUser.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered.")

    new_db_user = DBUser(
        username=user_data.username, hashed_password=hash_password(user_data.password),
        is_admin=user_data.is_admin,
        lollms_model_name=user_data.lollms_model_name,
        safe_store_vectorizer=user_data.safe_store_vectorizer
    )
    try:
        db.add(new_db_user); db.commit(); db.refresh(new_db_user)
        return new_db_user
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")

@admin_router.post("/users/{user_id}/reset-password")
async def admin_reset_user_password(user_id: int, payload: UserPasswordResetAdmin, db: Session = Depends(get_db)) -> Dict[str, str]:
    """(Admin) Resets the password for a specified user."""
    user_to_update = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_update: raise HTTPException(status_code=404, detail="User not found.")
    user_to_update.hashed_password = hash_password(payload.new_password)
    try:
        db.commit()
        return {"message": f"Password for user '{user_to_update.username}' reset."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")

@admin_router.delete("/users/{user_id}")
async def admin_remove_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)) -> Dict[str, str]:
    """(Admin) Removes a user and their associated data from the system."""
    user_to_delete = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_delete: raise HTTPException(status_code=404, detail="User not found.")

    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and user_to_delete.username == initial_admin_username and user_to_delete.is_admin:
        raise HTTPException(status_code=403, detail="Initial superadmin cannot be deleted.")
    if user_to_delete.username == current_admin.username:
        raise HTTPException(status_code=403, detail="Administrators cannot delete themselves.")

    try:
        user_data_dir = get_user_data_root(user_to_delete.username)
        if user_data_dir.exists(): shutil.rmtree(user_data_dir)
    except HTTPException: print(f"WARNING: Could not get data root for {user_to_delete.username}.")
    except OSError as e: print(f"ERROR: Failed to delete data dir for {user_to_delete.username}: {e}")

    try:
        db.delete(user_to_delete); db.commit()
        if user_to_delete.username in user_sessions: del user_sessions[user_to_delete.username]
        return {"message": f"User '{user_to_delete.username}' deleted."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
app.include_router(admin_router)


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    host = SERVER_CONFIG.get("host", "127.0.0.1")
    port = int(SERVER_CONFIG.get("port", 9642))

    try: APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"CRITICAL: Could not create main data directory {APP_DATA_DIR}: {e}")

    print(f"--- Simplified LoLLMs Chat API Server (v{APP_VERSION}) ---")
    print(f"Access UI at: http://{host}:{port}/")
    print(f"Access Admin Panel at: http://{host}:{port}/admin (requires admin login)")
    print("--------------------------------------------------------------------")
    uvicorn.run("main:app", host=host, port=port, reload=False)
