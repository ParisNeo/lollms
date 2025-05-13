# -*- coding: utf-8 -*-
# Project name: simplified_lollms
# File path: main.py
# Author: ParisNeo
# Creation date: 2025-05-08
# Description: Main FastAPI application for a multi-user LoLLMs and SafeStore
# chat service. Provides API endpoints for user authentication, discussion
# management (including starring and message grading), LLM interaction
# (via lollms-client) with enriched message metadata, RAG (via safe_store),
# file management for RAG, data import/export, and administrative user management.

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
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    JSONResponse,
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, constr, field_validator
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename

# Local Application Imports
from database_setup import (
    User as DBUser,
    UserStarredDiscussion,
    UserMessageGrade,  # Added import
    init_database,
    get_db,
    hash_password,
    DATABASE_URL_CONFIG_KEY,
)
from lollms_client import (
    LollmsClient,
    MSG_TYPE,
    LollmsDiscussion as LollmsClientDiscussion,
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
APP_VERSION = "1.4.0"  # Incremented version (feat: enriched messages, grading)

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


# --- Enriched Application Data Models ---
@dataclass
class AppLollmsMessage:
    """Represents a single message with enriched metadata for persistence."""

    sender: str
    content: str
    id: str = dataclass_field(default_factory=lambda: str(uuid.uuid4()))
    parent_message_id: Optional[str] = None  # For threading/resends
    # For LLM messages
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    # User-specific grade is handled in UserMessageGrade table
    # but we can store an aggregate or default grade here if needed for non-user views
    # For simplicity, we'll fetch user-specific grade dynamically when needed.

    def to_dict(self) -> Dict[str, Any]:
        """Converts the message to a dictionary."""
        data = {
            "sender": self.sender,
            "content": self.content,
            "id": self.id,
            "parent_message_id": self.parent_message_id,
            "binding_name": self.binding_name,
            "model_name": self.model_name,
            "token_count": self.token_count,
        }
        # Filter out None values for cleaner YAML/JSON
        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppLollmsMessage":
        """Creates a message from a dictionary."""
        return cls(
            sender=data.get("sender", "unknown"), # Provide default if missing
            content=data.get("content", ""),     # Provide default if missing
            id=data.get("id", str(uuid.uuid4())),
            parent_message_id=data.get("parent_message_id"),
            binding_name=data.get("binding_name"),
            model_name=data.get("model_name"),
            token_count=data.get("token_count"),
        )


class AppLollmsDiscussion:
    """Manages a discussion (a list of AppLollmsMessage) for persistence."""

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

    def add_message(
        self,
        sender: str,
        content: str,
        parent_message_id: Optional[str] = None,
        binding_name: Optional[str] = None,
        model_name: Optional[str] = None,
        token_count: Optional[int] = None,
    ) -> AppLollmsMessage:
        """Adds a message with enriched metadata to the discussion."""
        message = AppLollmsMessage(
            sender=sender,
            content=content,
            parent_message_id=parent_message_id,
            binding_name=binding_name,
            model_name=model_name,
            token_count=token_count,
        )
        self.messages.append(message)
        return message

    def edit_message(self, message_id: str, new_content: str) -> bool:
        """Edits an existing message's content by its ID."""
        for msg in self.messages:
            if msg.id == message_id:
                msg.content = new_content
                # Potentially re-calculate token_count if content changes
                if msg.sender.lower() != self.lollms_client.user_name.lower(): # AI message
                    try:
                        msg.token_count = self.lollms_client.count_tokens(new_content)
                    except Exception:
                        msg.token_count = len(new_content) // 3 # Fallback
                return True
        return False

    def delete_message(self, message_id: str) -> bool:
        original_len = len(self.messages)
        self.messages = [msg for msg in self.messages if msg.id != message_id]
        return len(self.messages) < original_len

    def _generate_title_from_messages_if_needed(self) -> None:
        is_generic_title = (
            self.title.startswith("New Discussion")
            or self.title.startswith("Imported")
            or self.title.startswith("Discussion ")
            or not self.title.strip()
        )
        if is_generic_title and self.messages:
            first_user_message_content = next(
                (
                    m.content
                    for m in self.messages
                    if m.sender.lower() == self.lollms_client.user_name.lower()
                ),
                None,
            )
            if first_user_message_content:
                new_title_base = first_user_message_content.strip().split("\n")[0]
                max_title_len = 50
                new_title = (
                    (new_title_base[: max_title_len - 3] + "...")
                    if len(new_title_base) > max_title_len
                    else new_title_base
                )
                if new_title:
                    self.title = new_title

    def to_dict(self) -> Dict[str, Any]:
        self._generate_title_from_messages_if_needed()
        return {
            "discussion_id": self.discussion_id,
            "title": self.title,
            "messages": [message.to_dict() for message in self.messages],
        }

    def save_to_disk(self, file_path: Union[str, Path]) -> None:
        data_to_save = self.to_dict()
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            yaml.dump(
                data_to_save,
                file,
                sort_keys=False,
                allow_unicode=True,
                Dumper=yaml.SafeDumper,
            )

    @classmethod
    def load_from_disk(
        cls, lollms_client_instance: LollmsClient, file_path: Union[str, Path]
    ) -> Optional["AppLollmsDiscussion"]:
        actual_path = Path(file_path)
        if not actual_path.exists():
            print(f"WARNING: Discussion file not found: {actual_path}")
            return None
        try:
            with open(actual_path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file)
        except (yaml.YAMLError, IOError) as e:
            print(f"ERROR: Could not load/parse discussion from {actual_path}: {e}")
            return None

        if not isinstance(data, dict): # Handle old list-based format
            print(f"WARNING: Old discussion format in {actual_path}. Attempting migration.")
            disc_id_from_path = actual_path.stem
            discussion = cls(
                lollms_client_instance,
                discussion_id=disc_id_from_path,
                title=f"Imported {disc_id_from_path[:8]}",
            )
            if isinstance(data, list): # Old format was a list of messages
                for msg_data in data:
                    if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                        discussion.messages.append(AppLollmsMessage.from_dict(msg_data)) # Handles new fields with defaults
            discussion._generate_title_from_messages_if_needed()
            return discussion

        # New dictionary-based format
        discussion_id = data.get("discussion_id", actual_path.stem)
        title = data.get("title", f"Imported {discussion_id[:8]}")
        discussion = cls(
            lollms_client_instance, discussion_id=discussion_id, title=title
        )
        loaded_messages_data = data.get("messages", [])
        if isinstance(loaded_messages_data, list):
            for msg_data in loaded_messages_data:
                if isinstance(msg_data, dict) and "sender" in msg_data and "content" in msg_data:
                    discussion.messages.append(AppLollmsMessage.from_dict(msg_data))
                else:
                    print(f"WARNING: Skipping malformed message data in {actual_path}: {msg_data}")
        
        if (not discussion.title or discussion.title.startswith("Imported ") or discussion.title.startswith("New Discussion ")):
            discussion._generate_title_from_messages_if_needed()
        return discussion

    def prepare_query_for_llm(
        self, current_prompt_text: str, max_total_tokens: Optional[int] = None
    ) -> str:
        lc = self.lollms_client
        if max_total_tokens is None:
            max_total_tokens = getattr(
                lc, "ctx_size", LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096)
            )

        client_discussion = LollmsClientDiscussion(lc)
        for app_msg in self.messages: # Use AppLollmsMessage attributes
            client_discussion.add_message(
                sender=app_msg.sender,
                content=app_msg.content,
                # LollmsClientDiscussion doesn't use these extra fields directly for formatting
            )

        user_prefix = f"{lc.separator_template}{lc.user_name}"
        ai_prefix = f"\n{lc.separator_template}{lc.ai_name}\n"
        current_turn_formatted = f"{user_prefix}\n{current_prompt_text}{ai_prefix}"
        try:
            current_turn_tokens = self.lollms_client.count_tokens(current_turn_formatted)
        except Exception:
            current_turn_tokens = len(current_turn_formatted) // 3

        tokens_for_history = max_total_tokens - current_turn_tokens
        if tokens_for_history < 0: tokens_for_history = 0
        
        history_text = client_discussion.format_discussion(max_allowed_tokens=tokens_for_history)
        full_prompt = f"{history_text}{user_prefix}\n{current_prompt_text}{ai_prefix}"
        return full_prompt


# --- Pydantic Models for API ---
class UserAuthDetails(BaseModel):
    username: str
    is_admin: bool
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    lollms_client_ai_name: Optional[str] = None

class UserCreateAdmin(BaseModel):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8)
    is_admin: bool = False
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None

class UserPasswordResetAdmin(BaseModel):
    new_password: constr(min_length=8)

class UserPublic(BaseModel):
    id: int
    username: str
    is_admin: bool
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None
    model_config = {"from_attributes": True}

class DiscussionInfo(BaseModel):
    id: str
    title: str
    is_starred: bool

class DiscussionTitleUpdate(BaseModel):
    title: constr(min_length=1, max_length=255)

class MessageOutput(BaseModel):
    """API output for messages, including user-specific grade."""
    id: str
    sender: str
    content: str
    parent_message_id: Optional[str] = None
    binding_name: Optional[str] = None
    model_name: Optional[str] = None
    token_count: Optional[int] = None
    user_grade: int = 0 # User's specific grade for this message

    @field_validator('user_grade', mode='before')
    def provide_default_grade(cls, value):
        return value if value is not None else 0


class MessageContentUpdate(BaseModel):
    content: str

class MessageGradeUpdate(BaseModel):
    """Request to update a message's grade (increment/decrement by 1)."""
    change: int # Should be 1 (upvote) or -1 (downvote)

    @field_validator('change')
    def change_must_be_one_or_minus_one(cls, value):
        if value not in [1, -1]:
            raise ValueError('Grade change must be 1 or -1')
        return value

class SafeStoreDocumentInfo(BaseModel):
    filename: str

class DiscussionExportRequest(BaseModel):
    discussion_ids: Optional[List[str]] = None

class ExportedMessageData(AppLollmsMessage): # Inherits to_dict, from_dict
    """Message structure within the exported JSON file."""
    # user_grades will be a list of {user_id (or username for privacy), grade}
    # This is handled during export/import logic, not directly in this Pydantic model for to_dict()
    # For export, we will add a 'grades_by_user' field if any grades exist.
    pass


class ExportData(BaseModel):
    exported_by_user: str
    export_timestamp: str
    application_version: str
    user_settings_at_export: Dict[str, Optional[str]]
    safestore_info: Dict[str, Any]
    discussions: List[Dict[str, Any]] # Each dict is an AppLollmsDiscussion.to_dict()
                                      # potentially augmented with grades_by_user for messages.

class DiscussionImportRequest(BaseModel):
    discussion_ids_to_import: List[str]

# --- Global User Session Management & Locks ---
user_sessions: Dict[str, Dict[str, Any]] = {}
# Lock for message grading to prevent race conditions on the DB UserMessageGrade table
# This is a simple global lock; for higher concurrency, per-message or per-user locks might be better.
message_grade_lock = threading.Lock()

# --- FastAPI Application Setup ---
app = FastAPI(
    title="Simplified LoLLMs Chat API",
    description="API for a multi-user LoLLMs and SafeStore chat application with RAG, file management, starring, message grading, and data import/export.",
    version=APP_VERSION,
)
security = HTTPBasic()

# --- FastAPI Event Handlers ---
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
            default_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
            default_vectorizer = SAFE_STORE_DEFAULTS.get("global_default_vectorizer")
            new_admin = DBUser(
                username=admin_username, hashed_password=hashed_admin_pass, is_admin=True,
                lollms_model_name=default_model, safe_store_vectorizer=default_vectorizer
            )
            db.add(new_admin); db.commit()
            print(f"INFO: Initial admin user '{admin_username}' created successfully.")
        else:
            print(f"INFO: Initial admin user '{admin_username}' already exists.")
    except Exception as e:
        print(f"ERROR: Failed during initial admin user setup: {e}")
        traceback.print_exc()
    finally:
        if db: db.close()

# --- User-specific Path Helpers --- (Unchanged)
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

def get_user_safestore_documents_path(username: str) -> Path:
    path = get_user_data_root(username) / "safestore_documents"
    path.mkdir(parents=True, exist_ok=True)
    return path

# --- Authentication Dependencies --- (Unchanged)
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
        user_sessions[username] = {
            "lollms_client": None, "safe_store_instance": None,
            "discussions": {}, "discussion_titles": {},
            "active_vectorizer": initial_vectorizer, "lollms_model_name": initial_lollms_model,
        }
    lc = get_user_lollms_client(username)
    ai_name_for_user = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))
    if not user_sessions[username].get("discussions"): _load_user_discussions(username)
    return UserAuthDetails(
        username=username, is_admin=db_user.is_admin,
        lollms_model_name=user_sessions[username]["lollms_model_name"],
        safe_store_vectorizer=user_sessions[username]["active_vectorizer"],
        lollms_client_ai_name=ai_name_for_user
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required.")
    return current_user

# --- Helper Functions for User-Specific Services --- (get_user_lollms_client, get_user_safe_store are Unchanged)
def get_user_lollms_client(username: str) -> LollmsClient:
    session = user_sessions.get(username)
    if not session:
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
            client_params = {
                "binding_name": binding_name, "model_name": model_name, "host_address": host_address,
                "ctx_size": ctx_size, "service_key": service_key, "user_name": user_name_conf, "ai_name": ai_name_conf
            }
            if temperature_conf is not None: client_params["temperature"] = temperature_conf
            if top_k_conf is not None: client_params["top_k"] = top_k_conf
            if top_p_conf is not None: client_params["top_p"] = top_p_conf
            lc = LollmsClient(**client_params)
            session["lollms_client"] = lc
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize LLM Client: {str(e)}")
    return cast(LollmsClient, session["lollms_client"])

def get_user_safe_store(username: str) -> safe_store.SafeStore:
    if safe_store is None:
        raise HTTPException(status_code=501, detail="SafeStore library not installed. RAG is disabled.")
    session = user_sessions.get(username)
    if not session:
        raise HTTPException(status_code=500, detail="User session not found for SafeStore.")
    if session.get("safe_store_instance") is None:
        user_data_path = get_user_data_root(username)
        ss_db_path = user_data_path / "vector_store.db"
        encryption_key = SAFE_STORE_DEFAULTS.get("encryption_key")
        log_level_str = SAFE_STORE_DEFAULTS.get("log_level", "INFO").upper()
        ss_log_level = getattr(SafeStoreLogLevel, log_level_str, SafeStoreLogLevel.INFO) if SafeStoreLogLevel else None
        try:
            ss_params = {"db_path": ss_db_path, "encryption_key": encryption_key}
            if ss_log_level is not None: ss_params["log_level"] = ss_log_level
            ss_instance = safe_store.SafeStore(**ss_params)
            session["safe_store_instance"] = ss_instance
        except safe_store.ConfigurationError as e:
            raise HTTPException(status_code=500, detail=f"SafeStore configuration error: {str(e)}.")
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Could not initialize SafeStore: {str(e)}")
    return cast(safe_store.SafeStore, session["safe_store_instance"])

# --- Discussion Management Helper Functions --- (_load_user_discussions, get_user_discussion, save_user_discussion are Unchanged)
def _load_user_discussions(username: str) -> None:
    try: lc = get_user_lollms_client(username)
    except HTTPException as e:
        print(f"ERROR: Cannot load discussions for {username}; LollmsClient unavailable: {e.detail}")
        if username in user_sessions:
            user_sessions[username]["discussions"] = {}; user_sessions[username]["discussion_titles"] = {}
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
        else: discussion_id = str(uuid.uuid4()) # Regenerate valid ID if creating
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
    try: uuid.UUID(discussion_id)
    except ValueError: return
    safe_discussion_filename = secure_filename(f"{discussion_id}.yaml")
    if not safe_discussion_filename.endswith(".yaml") or safe_discussion_filename == ".yaml": return
    file_path = get_user_discussion_path(username) / safe_discussion_filename
    try:
        discussion_obj.save_to_disk(file_path)
        if username in user_sessions: user_sessions[username]["discussion_titles"][discussion_id] = discussion_obj.title
    except Exception as e:
        traceback.print_exc()

# --- Root and Static File Endpoints --- (Unchanged)
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index_html(request: Request) -> FileResponse:
    index_path = Path("index.html").resolve()
    if not index_path.is_file(): raise HTTPException(status_code=404, detail="index.html not found.")
    return FileResponse(index_path)

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

try:
    locales_path = Path("locales").resolve()
    if locales_path.is_dir(): app.mount("/locales", StaticFiles(directory=locales_path, html=False), name="locales")
    else: print("WARNING: 'locales' directory not found. Localization files will not be served.")
except Exception as e: print(f"ERROR: Failed to mount locales directory: {e}")

# --- Authentication API --- (Unchanged)
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
@auth_router.get("/me", response_model=UserAuthDetails)
async def get_my_details(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    return current_user
@auth_router.post("/logout") # Can be POST or GET, POST is slightly more conventional for actions
async def logout(response: Response, current_user: UserAuthDetails = Depends(get_current_active_user)) -> Dict[str, str]:
    """
    Logs out the current user by clearing their server-side session data.
    The client is expected to handle redirection or page reload.
    """
    username = current_user.username
    if username in user_sessions:
        del user_sessions[username]
        print(f"INFO: User '{username}' session cleared (logged out).")
       
    return {"message": "Logout successful. Session cleared."}
app.include_router(auth_router)

# --- Discussion API ---
discussion_router = APIRouter(prefix="/api/discussions", tags=["Discussions"])

@discussion_router.get("", response_model=List[DiscussionInfo])
async def list_all_discussions(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DiscussionInfo]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found in DB.")
    titles_map = user_sessions[username].get("discussion_titles", {})
    starred_ids = {star.discussion_id for star in db.query(UserStarredDiscussion.discussion_id).filter(UserStarredDiscussion.user_id == user_id).all()}
    return [DiscussionInfo(id=disc_id, title=title, is_starred=(disc_id in starred_ids)) for disc_id, title in titles_map.items()]

@discussion_router.post("", response_model=DiscussionInfo, status_code=201)
async def create_new_discussion(current_user: UserAuthDetails = Depends(get_current_active_user)) -> DiscussionInfo:
    username = current_user.username
    discussion_id = str(uuid.uuid4())
    discussion_obj = get_user_discussion(username, discussion_id, create_if_missing=True)
    if not discussion_obj: raise HTTPException(status_code=500, detail="Failed to create new discussion.")
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=False)

@discussion_router.get("/{discussion_id}", response_model=List[MessageOutput])
async def get_messages_for_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[MessageOutput]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")

    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    # Fetch all grades for this user and this discussion in one go
    user_grades_for_discussion = {
        grade.message_id: grade.grade
        for grade in db.query(UserMessageGrade.message_id, UserMessageGrade.grade)
        .filter(UserMessageGrade.user_id == user_id, UserMessageGrade.discussion_id == discussion_id)
        .all()
    }
    
    # Map AppLollmsMessage to MessageOutput, including user_grade
    messages_output = []
    for msg in discussion_obj.messages:
        user_grade = user_grades_for_discussion.get(msg.id, 0)
        messages_output.append(
            MessageOutput(
                id=msg.id, sender=msg.sender, content=msg.content,
                parent_message_id=msg.parent_message_id,
                binding_name=msg.binding_name, model_name=msg.model_name,
                token_count=msg.token_count, user_grade=user_grade
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
    return DiscussionInfo(id=discussion_id, title=discussion_obj.title, is_starred=is_starred)

@discussion_router.delete("/{discussion_id}", status_code=200)
async def delete_specific_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
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
    try:
        db.query(UserStarredDiscussion).filter_by(discussion_id=discussion_id).delete()
        db.query(UserMessageGrade).filter_by(discussion_id=discussion_id).delete() # Also delete grades
        db.commit()
    except Exception as e_db:
        db.rollback()
        print(f"ERROR: Failed to delete DB entries for discussion {discussion_id}: {e_db}")
    return {"message": f"Discussion '{discussion_id}' deleted successfully."}

# Star/Unstar Endpoints (Unchanged from previous version)
@discussion_router.post("/{discussion_id}/star", status_code=201)
async def star_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    if not get_user_discussion(username, discussion_id): raise HTTPException(status_code=404, detail="Discussion not found.")
    if db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first():
        return {"message": "Discussion already starred."}
    new_star = UserStarredDiscussion(user_id=user_id, discussion_id=discussion_id)
    try:
        db.add(new_star); db.commit()
        return {"message": "Discussion starred successfully."}
    except IntegrityError: db.rollback(); return {"message": "Discussion already starred (race condition handled)."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"Database error: {e}")

@discussion_router.delete("/{discussion_id}/star", status_code=200)
async def unstar_discussion(discussion_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    star_to_delete = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=discussion_id).first()
    if not star_to_delete: return {"message": "Discussion was not starred."}
    try:
        db.delete(star_to_delete); db.commit()
        return {"message": "Discussion unstarred successfully."}
    except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"Database error: {e}")

# Chat Endpoint
@discussion_router.post("/{discussion_id}/chat")
async def chat_in_existing_discussion(
    discussion_id: str,
    prompt: str = Form(...),
    use_rag: bool = Form(False),
    parent_message_id: Optional[str] = Form(None), # Added parent_message_id
    current_user: UserAuthDetails = Depends(get_current_active_user),
) -> StreamingResponse:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj:
        raise HTTPException(status_code=404, detail=f"Discussion '{discussion_id}' not found.")

    lc = get_user_lollms_client(username)
    
    # Add user message with new metadata
    user_token_count = 0
    try: user_token_count =  lc.count_tokens(prompt)
    except: user_token_count = len(prompt) // 3

    discussion_obj.add_message(
        sender=lc.user_name, content=prompt, parent_message_id=parent_message_id,
        token_count=user_token_count
    )

    final_prompt_for_llm = prompt # RAG logic remains similar
    if use_rag and safe_store:
        active_vectorizer = user_sessions[username].get("active_vectorizer")
        if active_vectorizer:
            ss = get_user_safe_store(username)
            try:
                with ss: rag_results = ss.query(prompt, vectorizer_name=active_vectorizer, top_k=3)
                if rag_results:
                    context_str = "\n\nRelevant context from documents:\n"; max_rag_len, current_rag_len, sources = 2000, 0, set()
                    for i, res in enumerate(rag_results):
                        chunk_text = res.get('chunk_text',''); file_name = Path(res.get('file_path','?')).name
                        if current_rag_len + len(chunk_text) > max_rag_len and i > 0: context_str += f"... (truncated {len(rag_results) - i} more results)\n"; break
                        context_str += f"{i+1}. From '{file_name}': {chunk_text}\n"; current_rag_len += len(chunk_text); sources.add(file_name)
                    final_prompt_for_llm = (f"User question: {prompt}\n\n"
                                           f"Use the following context from ({', '.join(sorted(list(sources)))}) to answer if relevant:\n{context_str.strip()}")
            except Exception as e: print(f"ERROR: RAG query failed for {username}: {e}")
        else: print(f"WARNING: RAG requested by {username} but no active vectorizer.")
    elif use_rag and not safe_store: print(f"WARNING: RAG requested by {username} but safe_store is not available.")

    main_loop = asyncio.get_event_loop()
    stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    shared_state = {"accumulated_ai_response": "", "generation_error": None, "final_message_id": None}

    async def stream_generator() -> AsyncGenerator[str, None]:
        def llm_callback(chunk: str, msg_type: MSG_TYPE, params: Optional[Dict[str, Any]] = None) -> bool:
            if msg_type == MSG_TYPE.MSG_TYPE_CHUNK:
                shared_state["accumulated_ai_response"] += chunk
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "chunk", "content": chunk}) + "\n")
            elif msg_type in (MSG_TYPE.MSG_TYPE_EXCEPTION, MSG_TYPE.MSG_TYPE_ERROR):
                err_content = f"LLM Error: {str(chunk)}"
                shared_state["generation_error"] = err_content
                main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_content}) + "\n")
                return False
            elif msg_type == MSG_TYPE.MSG_TYPE_FULL_INVISIBLE_TO_USER: # Example: Final token count from some bindings
                if params and "final_message_id" in params: shared_state["final_message_id"] = params["final_message_id"] # If binding provides it
            elif msg_type == MSG_TYPE.MSG_TYPE_FINISHED_MESSAGE:
                return False
            return True

        generation_thread: Optional[threading.Thread] = None
        try:
            full_prompt_to_llm = discussion_obj.prepare_query_for_llm(final_prompt_for_llm)
            def blocking_call():
                try:
                    # Model and binding info for this specific generation
                    current_binding_name = lc.binding.binding_name if lc.binding else "unknown_binding"
                    current_model_name = lc.binding.model_name if lc.binding and hasattr(lc.binding, "model_name") else session.get("lollms_model_name", "unknown_model")

                    # Store these with the message *before* generation starts
                    # The message object itself will be added to discussion_obj *after* stream
                    shared_state["binding_name"] = current_binding_name
                    shared_state["model_name"] = current_model_name
                    
                    lc.generate_text(prompt=full_prompt_to_llm, stream=True, streaming_callback=llm_callback)
                except Exception as e_gen:
                    err_msg = f"LLM generation failed: {str(e_gen)}"
                    shared_state["generation_error"] = err_msg
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
                finally:
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)
            
            generation_thread = threading.Thread(target=blocking_call, daemon=True)
            generation_thread.start()
            while True:
                item = await stream_queue.get()
                if item is None: stream_queue.task_done(); break
                yield item; stream_queue.task_done()
            
            if generation_thread: generation_thread.join(timeout=5)

            ai_response_content = shared_state["accumulated_ai_response"]
            ai_token_count = 0
            try: ai_token_count = lc.count_tokens(ai_response_content)
            except: ai_token_count = len(ai_response_content) // 3
            
            # Determine parent ID for AI's response: the last user message
            ai_parent_id = discussion_obj.messages[-1].id if discussion_obj.messages and discussion_obj.messages[-1].sender == lc.user_name else None

            if ai_response_content and not shared_state["generation_error"]:
                ai_message = discussion_obj.add_message(
                    sender=lc.ai_name, content=ai_response_content,
                    parent_message_id=ai_parent_id,
                    binding_name=shared_state.get("binding_name"),
                    model_name=shared_state.get("model_name"),
                    token_count=ai_token_count
                )
                if shared_state.get("final_message_id"): # If binding provided a more specific ID
                    ai_message.id = shared_state["final_message_id"]

            elif shared_state["generation_error"]:
                 discussion_obj.add_message(sender="system", content=shared_state["generation_error"], parent_message_id=ai_parent_id)
            
            save_user_discussion(username, discussion_id, discussion_obj)
        except Exception as e_outer:
            error_msg = f"Chat stream error: {str(e_outer)}"; traceback.print_exc()
            try: discussion_obj.add_message(sender="system", content=error_msg); save_user_discussion(username, discussion_id, discussion_obj)
            except Exception as save_err: print(f"ERROR: Failed to save discussion after outer stream error: {save_err}")
            yield json.dumps({"type": "error", "content": error_msg}) + "\n"
        finally:
            if generation_thread and generation_thread.is_alive(): print(f"WARNING: LLM gen thread for {username} still alive.")
    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

# Message Grading Endpoint
@discussion_router.put("/{discussion_id}/messages/{message_id}/grade", response_model=MessageOutput)
async def grade_discussion_message(
    discussion_id: str, message_id: str, grade_update: MessageGradeUpdate,
    current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> MessageOutput:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")

    # Find the message in the YAML discussion file to return its details
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj: raise HTTPException(status_code=404, detail="Discussion not found.")
    
    target_message = next((msg for msg in discussion_obj.messages if msg.id == message_id), None)
    if not target_message: raise HTTPException(status_code=404, detail="Message not found in discussion.")
    
    # Only AI messages can be graded
    lc = get_user_lollms_client(username)
    if target_message.sender == lc.user_name:
        raise HTTPException(status_code=400, detail="User messages cannot be graded.")

    with message_grade_lock: # Ensure atomic update for the grade
        grade_record = db.query(UserMessageGrade).filter_by(
            user_id=user_id, discussion_id=discussion_id, message_id=message_id
        ).first()

        if grade_record:
            grade_record.grade += grade_update.change
        else:
            grade_record = UserMessageGrade(
                user_id=user_id, discussion_id=discussion_id,
                message_id=message_id, grade=grade_update.change
            )
            db.add(grade_record)
        
        try:
            db.commit(); db.refresh(grade_record)
            current_user_grade = grade_record.grade
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"DB error updating grade: {e}")

    return MessageOutput(
        id=target_message.id, sender=target_message.sender, content=target_message.content,
        parent_message_id=target_message.parent_message_id,
        binding_name=target_message.binding_name, model_name=target_message.model_name,
        token_count=target_message.token_count, user_grade=current_user_grade
    )

# Message Edit/Delete (Unchanged logic, but MessageOutput includes grade)
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
        
    return MessageOutput(
        id=updated_msg.id, sender=updated_msg.sender, content=updated_msg.content,
        parent_message_id=updated_msg.parent_message_id, binding_name=updated_msg.binding_name,
        model_name=updated_msg.model_name, token_count=updated_msg.token_count, user_grade=user_grade
    )

@discussion_router.delete("/{discussion_id}/messages/{message_id}", status_code=200)
async def delete_discussion_message(discussion_id: str, message_id: str, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username
    discussion_obj = get_user_discussion(username, discussion_id)
    if not discussion_obj or not discussion_obj.delete_message(message_id):
        raise HTTPException(status_code=404, detail="Message or discussion not found.")
    save_user_discussion(username, discussion_id, discussion_obj)
    # Also delete grades associated with this message for ALL users
    try:
        db.query(UserMessageGrade).filter_by(discussion_id=discussion_id, message_id=message_id).delete()
        db.commit()
    except Exception as e: db.rollback(); print(f"WARN: Could not delete grades for message {message_id}: {e}")
    return {"message": "Message deleted successfully."}

# Export/Import Data
@discussion_router.post("/export", response_model=ExportData)
async def export_user_data(export_request: DiscussionExportRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> ExportData:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    user_settings = {"lollms_model_name": user_sessions[username]["lollms_model_name"], "safe_store_vectorizer": user_sessions[username]["active_vectorizer"]}
    safestore_info = {"vectorizers": [], "documents_info": [], "error": None}
    if safe_store:
        try:
            ss = get_user_safe_store(username)
            with ss:
                safestore_info["vectorizers"] = ss.list_vectorization_methods()
                safestore_info["documents_info"] = [{"filename": Path(d["file_path"]).name, "metadata": d.get("metadata")} for d in ss.list_documents() if "file_path" in d]
        except Exception as e: safestore_info["error"] = str(e)
    else: safestore_info["error"] = "SafeStore library not available."
    if not user_sessions[username].get("discussions"): _load_user_discussions(username)
    all_user_discussions_map = user_sessions[username].get("discussions", {})
    
    discussions_to_export_ids = set(all_user_discussions_map.keys())
    if export_request.discussion_ids is not None:
        discussions_to_export_ids &= set(export_request.discussion_ids)
        
    # Fetch all grades for the current user for the discussions being exported
    user_grades_for_export = {}
    if discussions_to_export_ids:
        grades_query = db.query(UserMessageGrade.discussion_id, UserMessageGrade.message_id, UserMessageGrade.grade)\
                         .filter(UserMessageGrade.user_id == user_id, UserMessageGrade.discussion_id.in_(discussions_to_export_ids)).all()
        for disc_id_db, msg_id_db, grade_db in grades_query:
            if disc_id_db not in user_grades_for_export: user_grades_for_export[disc_id_db] = {}
            user_grades_for_export[disc_id_db][msg_id_db] = grade_db

    discussions_data_list = []
    for disc_id in discussions_to_export_ids:
        disc_obj = all_user_discussions_map[disc_id]
        disc_dict = disc_obj.to_dict() # This is a List[AppLollmsMessage] effectively
        
        # Augment messages with their grades for this user
        grades_for_this_disc = user_grades_for_export.get(disc_id, {})
        augmented_messages = []
        for msg_data in disc_dict.get("messages", []):
            msg_id_yaml = msg_data.get("id")
            if msg_id_yaml and msg_id_yaml in grades_for_this_disc:
                msg_data["user_grade"] = grades_for_this_disc[msg_id_yaml] # Add grade to export
            augmented_messages.append(msg_data)
        disc_dict["messages"] = augmented_messages

        # Add starred status
        is_starred = db.query(UserStarredDiscussion).filter_by(user_id=user_id, discussion_id=disc_id).first() is not None
        disc_dict["is_starred"] = is_starred
        discussions_data_list.append(disc_dict)

    return ExportData(
        exported_by_user=username, export_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        application_version=APP_VERSION, user_settings_at_export=user_settings,
        safestore_info=safestore_info, discussions=discussions_data_list
    )

@discussion_router.post("/import", status_code=200)
async def import_user_data(
    import_file: UploadFile = File(...), import_request_json: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    username = current_user.username
    user_id = db.query(DBUser.id).filter(DBUser.username == username).scalar()
    if not user_id: raise HTTPException(status_code=404, detail="User not found.")
    try: import_request = DiscussionImportRequest.model_validate_json(import_request_json)
    except Exception as e: raise HTTPException(status_code=400, detail=f"Invalid import request format: {e}")
    if import_file.content_type != "application/json": raise HTTPException(status_code=400, detail="Invalid file type.")
    try:
        content = await import_file.read(); import_data = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError: raise HTTPException(status_code=400, detail="Invalid JSON file content.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Failed to read upload file: {e}")
    finally: await import_file.close()
    if not isinstance(import_data, dict) or "discussions" not in import_data: raise HTTPException(status_code=400, detail="Invalid export file format.")
    
    imported_discussions_data = import_data.get("discussions", [])
    if not isinstance(imported_discussions_data, list): raise HTTPException(status_code=400, detail="Format error: 'discussions' not a list.")

    lc = get_user_lollms_client(username); session = user_sessions[username]
    imported_count, skipped_count, errors = 0, 0, []
    if not session.get("discussions"): _load_user_discussions(username)

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
            messages_from_file = disc_data_from_file.get("messages", [])
            if isinstance(messages_from_file, list):
                for msg_data_from_file in messages_from_file:
                    if isinstance(msg_data_from_file, dict) and "sender" in msg_data_from_file and "content" in msg_data_from_file:
                        # AppLollmsMessage.from_dict will handle new fields with defaults
                        imported_message_obj = AppLollmsMessage.from_dict(msg_data_from_file)
                        imported_discussion_obj.messages.append(imported_message_obj)
                        
                        # Import grade if present for this message
                        imported_grade = msg_data_from_file.get("user_grade") # Grade from the exporting user
                        if imported_grade is not None and isinstance(imported_grade, int):
                             grade_rec = UserMessageGrade(user_id=user_id, discussion_id=new_discussion_id, message_id=imported_message_obj.id, grade=imported_grade)
                             db.add(grade_rec) # Add to session for batch commit
            
            save_user_discussion(username, new_discussion_id, imported_discussion_obj)
            session["discussions"][new_discussion_id] = imported_discussion_obj
            session["discussion_titles"][new_discussion_id] = imported_discussion_obj.title
            imported_count += 1
            if disc_data_from_file.get("is_starred", False):
                 star_rec = UserStarredDiscussion(user_id=user_id, discussion_id=new_discussion_id)
                 db.add(star_rec) # Add to session for batch commit
        except Exception as e_import:
            skipped_count += 1; errors.append({"original_id": original_id, "error": str(e_import)}); traceback.print_exc()
    try: db.commit() # Commit all added stars and grades
    except Exception as e_db: db.rollback(); errors.append({"DB_COMMIT_ERROR": str(e_db)})
    return {"message": f"Import finished. Imported: {imported_count}, Skipped/Errors: {skipped_count}.", "imported_count": imported_count, "skipped_count": skipped_count, "errors": errors}

app.include_router(discussion_router)

# --- LoLLMs Configuration API --- (Unchanged from previous version)
lollms_config_router = APIRouter(prefix="/api/config", tags=["LoLLMs Configuration"])
@lollms_config_router.get("/lollms-models", response_model=List[Dict[str, str]])
async def get_available_lollms_models(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[Dict[str, str]]:
    lc = get_user_lollms_client(current_user.username); models_set: set[str] = set()
    try:
        binding_models = lc.listModels()
        if isinstance(binding_models, list):
            for item in binding_models:
                if isinstance(item, str): 
                    models_set.add(item)
                elif isinstance(item, dict): 
                    name = item.get("name", item.get("id", item.get("model_name")))
                    models_set.add(name)
    except Exception as e: 
        print(f"WARNING: Could not list models from LollmsClient: {e}")
    user_model = user_sessions[current_user.username].get("lollms_model_name"); global_default_model = LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
    if user_model: models_set.add(user_model)
    if global_default_model: models_set.add(global_default_model)
    models_set.discard("")
    if not models_set and lc.binding is not None and "openai" in lc.binding.binding_name.lower(): models_set.update(["gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
    return [{"name": name} for name in sorted(list(models_set))] if models_set else [{"name": "No models found"}]

@lollms_config_router.post("/lollms-model")
async def set_user_lollms_model(model_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username; user_sessions[username]["lollms_model_name"] = model_name; user_sessions[username]["lollms_client"] = None
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user_record:
        db_user_record.lollms_model_name = model_name
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    else: raise HTTPException(status_code=404, detail="User not found for model update.")
    return {"message": f"Default LoLLMs model set to '{model_name}'. Client will re-initialize."}
app.include_router(lollms_config_router)

# --- SafeStore (RAG) API --- (Unchanged from previous version)
store_router = APIRouter(prefix="/api/store", tags=["SafeStore RAG & File Management"])
@store_router.get("/vectorizers", response_model=List[Dict[str,str]])
async def list_safe_store_vectorizers(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[Dict[str,str]]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    ss = get_user_safe_store(current_user.username)
    try:
        with ss: methods_in_db = ss.list_vectorization_methods(); possible_names = ss.list_possible_vectorizer_names()
        formatted_vectorizers = []; existing_method_names = set()
        for method_info in methods_in_db:
            name = method_info.get("method_name")
            if name: formatted_vectorizers.append({"name": name, "method_name": f"{name} (dim: {method_info.get('vector_dim', 'N/A')})"}); existing_method_names.add(name)
        for possible_name in possible_names:
            if possible_name not in existing_method_names:
                display_text = possible_name
                if possible_name.startswith("tfidf:"): display_text = f"{possible_name} (TF-IDF, auto-fit)"
                elif possible_name.startswith("st:"): display_text = f"{possible_name} (Sentence Transformer)"
                formatted_vectorizers.append({"name": possible_name, "method_name": display_text})
        final_list = []; seen_names = set()
        for fv in formatted_vectorizers:
            if fv["name"] not in seen_names: final_list.append(fv); seen_names.add(fv["name"])
        final_list.sort(key=lambda x: x["name"]); return final_list
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing vectorizers: {e}")

@store_router.get("/active-vectorizer", response_model=Dict[str, Optional[str]])
async def get_session_active_vectorizer(current_user: UserAuthDetails = Depends(get_current_active_user)) -> Dict[str, Optional[str]]:
    return {"active_vectorizer": user_sessions[current_user.username].get("active_vectorizer")}

@store_router.post("/active-vectorizer")
async def set_session_active_vectorizer(vectorizer_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> Dict[str, str]:
    username = current_user.username; user_sessions[username]["active_vectorizer"] = vectorizer_name
    db_user_record = db.query(DBUser).filter(DBUser.username == username).first()
    if db_user_record:
        db_user_record.safe_store_vectorizer = vectorizer_name
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
    else: raise HTTPException(status_code=404, detail="User not found.")
    return {"message": f"Active RAG vectorizer set to '{vectorizer_name}'."}

@store_router.post("/upload-files")
async def upload_rag_documents(files: List[UploadFile] = File(...), vectorizer_name: str = Form(...), current_user: UserAuthDetails = Depends(get_current_active_user)) -> JSONResponse:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    username = current_user.username; ss = get_user_safe_store(username); user_docs_path = get_user_safestore_documents_path(username)
    processed, errors_list = [], []
    try:
        with ss: all_vectorizers = {m['method_name'] for m in ss.list_vectorization_methods()} | set(ss.list_possible_vectorizer_names())
        if not (vectorizer_name in all_vectorizers or vectorizer_name.startswith("st:") or vectorizer_name.startswith("tfidf:")):
             raise HTTPException(status_code=400, detail=f"Vectorizer '{vectorizer_name}' not found or invalid format.")
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error checking vectorizer: {e}")
    for file_upload in files:
        s_filename = secure_filename(file_upload.filename or f"upload_{uuid.uuid4().hex[:8]}"); target_file_path = user_docs_path / s_filename
        try:
            target_file_path.parent.mkdir(parents=True, exist_ok=True)
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

@store_router.get("/files", response_model=List[SafeStoreDocumentInfo])
async def list_rag_documents(current_user: UserAuthDetails = Depends(get_current_active_user)) -> List[SafeStoreDocumentInfo]:
    if not safe_store: return []
    username = current_user.username; user_docs_path_resolved = get_user_safestore_documents_path(username).resolve(); ss = get_user_safe_store(username)
    managed_docs = []
    try:
        with ss: stored_meta = ss.list_documents()
        for doc_meta in stored_meta:
            original_path_str = doc_meta.get("file_path")
            if original_path_str:
                try:
                    if Path(original_path_str).resolve().parent == user_docs_path_resolved: managed_docs.append(SafeStoreDocumentInfo(filename=Path(original_path_str).name))
                except Exception: pass
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing RAG docs: {e}")
    managed_docs.sort(key=lambda x: x.filename); return managed_docs

@store_router.delete("/files/{filename}")
async def delete_rag_document(filename: str, current_user: UserAuthDetails = Depends(get_current_active_user)) -> Dict[str, str]:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    username = current_user.username; s_filename = secure_filename(filename)
    if not s_filename or s_filename != filename: raise HTTPException(status_code=400, detail="Invalid filename.")
    file_to_delete_path = get_user_safestore_documents_path(username) / s_filename
    if not file_to_delete_path.is_file(): raise HTTPException(status_code=404, detail=f"Document '{s_filename}' not found.")
    ss = get_user_safe_store(username)
    try:
        with ss: ss.delete_document_by_path(str(file_to_delete_path))
        file_to_delete_path.unlink()
        return {"message": f"Document '{s_filename}' deleted successfully."}
    except Exception as e:
        if file_to_delete_path.exists(): raise HTTPException(status_code=500, detail=f"Could not delete '{s_filename}': {e}")
        else: return {"message": f"Document '{s_filename}' file deleted, potential DB cleanup issue."}
app.include_router(store_router)

# --- Admin API --- (Unchanged from previous version)
admin_router = APIRouter(prefix="/api/admin", tags=["Administration"], dependencies=[Depends(get_current_admin_user)])
@admin_router.get("/users", response_model=List[UserPublic])
async def admin_get_all_users(db: Session = Depends(get_db)) -> List[DBUser]: return db.query(DBUser).all()
@admin_router.post("/users", response_model=UserPublic, status_code=201)
async def admin_add_new_user(user_data: UserCreateAdmin, db: Session = Depends(get_db)) -> DBUser:
    if db.query(DBUser).filter(DBUser.username == user_data.username).first(): raise HTTPException(status_code=400, detail="Username already registered.")
    new_db_user = DBUser(username=user_data.username, hashed_password=hash_password(user_data.password), is_admin=user_data.is_admin, lollms_model_name=user_data.lollms_model_name, safe_store_vectorizer=user_data.safe_store_vectorizer)
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
async def admin_remove_user(user_id: int, db: Session = Depends(get_db), current_admin: UserAuthDetails = Depends(get_current_admin_user)) -> Dict[str, str]:
    user_to_delete = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user_to_delete: raise HTTPException(status_code=404, detail="User not found.")
    initial_admin_username = INITIAL_ADMIN_USER_CONFIG.get("username")
    if initial_admin_username and user_to_delete.username == initial_admin_username and user_to_delete.is_admin: raise HTTPException(status_code=403, detail="Initial superadmin cannot be deleted.")
    if user_to_delete.username == current_admin.username: raise HTTPException(status_code=403, detail="Administrators cannot delete themselves.")
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

# --- Main Execution --- (Unchanged)
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
