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
from dataclasses import dataclass, field as dataclass_field
from werkzeug.utils import secure_filename

# Local Application Imports
from database_setup import (
    User as DBUser,
    UserStarredDiscussion,
    UserMessageGrade,
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
APP_VERSION = "1.5.0"  # Updated version for multimodal, datastores, LLM params, discussion sharing

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
                    try: msg.token_count = self.lollms_client.count_tokens(new_content)
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
        self, current_prompt_text: str, image_paths_for_llm: Optional[List[str]], max_total_tokens: Optional[int] = None
    ) -> str: # Image paths are handled by lollms_client directly from its generate_text method
        lc = self.lollms_client
        
        if max_total_tokens is None:
            max_total_tokens = getattr(lc, "ctx_size", LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096))

        client_discussion = LollmsClientDiscussion(lc)
        for app_msg in self.messages:
            client_discussion.add_message(sender=app_msg.sender, content=app_msg.content)

        user_prefix = f"{lc.separator_template}{lc.user_name}"
        ai_prefix = f"\n{lc.separator_template}{lc.ai_name}\n"
        current_turn_formatted_text_only = f"{user_prefix}\n{current_prompt_text}{ai_prefix}"
        
        # Token count needs to consider images if the binding does (some might add special tokens)
        # For simplicity, we'll count tokens for text only for history calculation.
        # The lollms-client's generate_text handles the actual image passing.
        try:
            current_turn_tokens = self.lollms_client.count_tokens(current_turn_formatted_text_only)
        except Exception:
            current_turn_tokens = len(current_turn_formatted_text_only) // 3 # Fallback

        tokens_for_history = max_total_tokens - current_turn_tokens
        if tokens_for_history < 0: tokens_for_history = 0
        
        history_text = client_discussion.format_discussion(max_allowed_tokens=tokens_for_history)
        full_prompt = f"{history_text}{user_prefix}\n{current_prompt_text}{ai_prefix}"
        return full_prompt


# --- Pydantic Models for API ---
class UserLLMParams(BaseModel):
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    llm_top_k: Optional[int] = Field(None, ge=1)
    llm_top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    llm_repeat_penalty: Optional[float] = Field(None, ge=0.0)
    llm_repeat_last_n: Optional[int] = Field(None, ge=0)

class UserAuthDetails(UserLLMParams):
    username: str
    is_admin: bool
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None # Default vectorizer for user
    lollms_client_ai_name: Optional[str] = None

class UserCreateAdmin(UserLLMParams):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=8)
    is_admin: bool = False
    lollms_model_name: Optional[str] = None
    safe_store_vectorizer: Optional[str] = None

class UserPasswordResetAdmin(BaseModel):
    new_password: constr(min_length=8)

class UserPublic(UserLLMParams):
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
    user_settings_at_export: Dict[str, Optional[Any]] # Includes LLM params
    # datastore info will be more complex: list of owned datastores (name, id, description)
    # and list of datastores shared with user (name, id, owner_username, description)
    datastores_info: Dict[str, Any] = Field(default_factory=dict)
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
            # Get default LLM params from config or use None
            def_temp = LOLLMS_CLIENT_DEFAULTS.get("temperature")
            def_top_k = LOLLMS_CLIENT_DEFAULTS.get("top_k")
            def_top_p = LOLLMS_CLIENT_DEFAULTS.get("top_p")
            def_rep_pen = LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty")
            def_rep_last_n = LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n")
            new_admin = DBUser(
                username=admin_username, hashed_password=hashed_admin_pass, is_admin=True,
                lollms_model_name=def_model, safe_store_vectorizer=def_vec,
                llm_temperature=def_temp, llm_top_k=def_top_k, llm_top_p=def_top_p,
                llm_repeat_penalty=def_rep_pen, llm_repeat_last_n=def_rep_last_n
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
        
        llm_params = {
            "temperature": db_user.llm_temperature if db_user.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            "top_k": db_user.llm_top_k if db_user.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
            "top_p": db_user.llm_top_p if db_user.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
            "repeat_penalty": db_user.llm_repeat_penalty if db_user.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
            "repeat_last_n": db_user.llm_repeat_last_n if db_user.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n"),
        }
        # Filter out None values from llm_params as LollmsClient expects actual values or omission
        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        user_sessions[username] = {
            "lollms_client": None, "safe_store_instances": {}, # Now a dict of datastore_id -> SafeStore instance
            "discussions": {}, "discussion_titles": {},
            "active_vectorizer": initial_vectorizer, # User's default, can be overridden per RAG use
            "lollms_model_name": initial_lollms_model,
            "llm_params": llm_params, # Store resolved LLM parameters
        }
    lc = get_user_lollms_client(username) # Ensures client is initialized with current params
    ai_name_for_user = getattr(lc, "ai_name", LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant"))
    if not user_sessions[username].get("discussions"): _load_user_discussions(username)

    # Populate UserAuthDetails with current LLM params from session
    session_llm_params = user_sessions[username].get("llm_params", {})
    return UserAuthDetails(
        username=username, is_admin=db_user.is_admin,
        lollms_model_name=user_sessions[username]["lollms_model_name"],
        safe_store_vectorizer=user_sessions[username]["active_vectorizer"],
        lollms_client_ai_name=ai_name_for_user,
        llm_temperature=session_llm_params.get("temperature"),
        llm_top_k=session_llm_params.get("top_k"),
        llm_top_p=session_llm_params.get("top_p"),
        llm_repeat_penalty=session_llm_params.get("repeat_penalty"),
        llm_repeat_last_n=session_llm_params.get("repeat_last_n"),
    )

def get_current_admin_user(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator privileges required.")
    return current_user

# --- Helper Functions for User-Specific Services ---
def get_user_lollms_client(username: str) -> LollmsClient:
    session = user_sessions.get(username)
    if not session: raise HTTPException(status_code=500, detail="User session not found for LollmsClient.")
    
    # Check if client needs re-initialization due to changed params
    # This simplistic check re-initializes if any core param differs or if client is None.
    # More sophisticated would be to compare all relevant params.
    force_reinit = session.get("lollms_client") is None
    
    current_model_name = session["lollms_model_name"]
    if not force_reinit and hasattr(session["lollms_client"], "model_name") and session["lollms_client"].model_name != current_model_name:
        force_reinit = True
    
    # TODO: Add checks for other LLM parameters if they changed
    # For now, model_name change is a primary trigger.
    
    if force_reinit:
        model_name = session["lollms_model_name"]
        binding_name = LOLLMS_CLIENT_DEFAULTS.get("binding_name", "lollms")
        host_address = LOLLMS_CLIENT_DEFAULTS.get("host_address")
        ctx_size = LOLLMS_CLIENT_DEFAULTS.get("ctx_size", 4096)
        service_key_env_name = LOLLMS_CLIENT_DEFAULTS.get("service_key_env_var")
        service_key = os.getenv(service_key_env_name) if service_key_env_name else None
        user_name_conf = LOLLMS_CLIENT_DEFAULTS.get("user_name", "user")
        ai_name_conf = LOLLMS_CLIENT_DEFAULTS.get("ai_name", "assistant")
        
        # Get user-specific or default LLM parameters from session
        client_init_params = session.get("llm_params", {}).copy() # Start with user/default params

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
            lc = LollmsClient(**client_init_params)
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
    locales_path = Path("locales").resolve()
    if locales_path.is_dir(): app.mount("/locales", StaticFiles(directory=locales_path, html=False), name="locales")
    else: print("WARNING: 'locales' directory not found. Localization files will not be served.")
except Exception as e: print(f"ERROR: Failed to mount locales directory: {e}")

# --- Authentication API ---
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
@auth_router.get("/me", response_model=UserAuthDetails)
async def get_my_details(current_user: UserAuthDetails = Depends(get_current_active_user)) -> UserAuthDetails: return current_user
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
                    # Store path relative to discussion_assets/<discussion_id>
                    final_image_references_for_message.append(persistent_filename)
                    llm_image_paths.append(str(persistent_abs_path))
                except Exception as e_move:
                    print(f"ERROR moving image {temp_abs_path} to {persistent_abs_path}: {e_move}")
            else:
                print(f"WARNING: Temporary image file not found: {temp_abs_path}")
    
    user_token_count = lc.count_tokens(prompt) if prompt else 0
    discussion_obj.add_message(
        sender=lc.user_name, content=prompt, parent_message_id=parent_message_id,
        token_count=user_token_count, image_references=final_image_references_for_message
    )

    final_prompt_for_llm = prompt
    if use_rag and safe_store:
        if not rag_datastore_id:
            # If discussion_obj has a default RAG datastore, use it.
            rag_datastore_id = discussion_obj.rag_datastore_id
            if not rag_datastore_id:
                # Fallback to user's default if discussion has no specific datastore set
                rag_datastore_id = user_sessions[username].get("active_vectorizer") # This seems like a misnomer, should be default_datastore_id
                                                                                 # For now, assume active_vectorizer means a concept of user's primary choice.
                                                                                 # This needs refinement if active_vectorizer is purely for choosing *which* vectorizer method,
                                                                                 # not *which* store. Let's assume the client UI has a way to set discussion_obj.rag_datastore_id
                if not rag_datastore_id:
                    print(f"WARNING: RAG requested by {username} but no datastore specified for discussion or user default.")


        if rag_datastore_id:
            try:
                ss = get_safe_store_instance(username, rag_datastore_id, db)
                # Determine which vectorizer to use. If datastore has only one, use it.
                # Otherwise, client might need to specify, or use user's default `safe_store_vectorizer`.
                # For now, let SafeStore pick its default or the only one available in that store.
                # A more advanced RAG query might allow specifying vectorizer for the given store.
                active_vectorizer_for_store = user_sessions[username].get("active_vectorizer") # User's general default vectorizer

                with ss: rag_results = ss.query(prompt, vectorizer_name=active_vectorizer_for_store, top_k=3) # Consider making vectorizer_name configurable per query/datastore
                if rag_results:
                    context_str = "\n\nRelevant context from documents:\n"; max_rag_len, current_rag_len, sources = 2000, 0, set()
                    for i, res in enumerate(rag_results):
                        chunk_text = res.get('chunk_text',''); file_name = Path(res.get('file_path','?')).name
                        if current_rag_len + len(chunk_text) > max_rag_len and i > 0: context_str += f"... (truncated {len(rag_results) - i} more results)\n"; break
                        context_str += f"{i+1}. From '{file_name}': {chunk_text}\n"; current_rag_len += len(chunk_text); sources.add(file_name)
                    final_prompt_for_llm = (f"User question: {prompt}\n\n"
                                           f"Use the following context from ({', '.join(sorted(list(sources)))}) to answer if relevant:\n{context_str.strip()}")
            except HTTPException as e_rag_access: # e.g. datastore not found or access denied
                print(f"INFO: RAG query skipped for {username} on datastore {rag_datastore_id}: {e_rag_access.detail}")
            except Exception as e: print(f"ERROR: RAG query failed for {username} on datastore {rag_datastore_id}: {e}")
        else: print(f"WARNING: RAG requested by {username} but no RAG datastore selected for this discussion or as user default.")
    elif use_rag and not safe_store: print(f"WARNING: RAG requested by {username} but safe_store is not available.")

    main_loop = asyncio.get_event_loop()
    stream_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    shared_state = {"accumulated_ai_response": "", "generation_error": None, "final_message_id": None, "binding_name": None, "model_name": None}

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
            elif msg_type == MSG_TYPE.MSG_TYPE_FULL_INVISIBLE_TO_USER:
                if params and "final_message_id" in params: shared_state["final_message_id"] = params["final_message_id"]
            elif msg_type == MSG_TYPE.MSG_TYPE_FINISHED_MESSAGE: return False
            return True

        generation_thread: Optional[threading.Thread] = None
        try:
            full_prompt_to_llm = discussion_obj.prepare_query_for_llm(final_prompt_for_llm, llm_image_paths)
            def blocking_call():
                try:
                    shared_state["binding_name"] = lc.binding.binding_name if lc.binding else "unknown_binding"
                    shared_state["model_name"] = lc.binding.model_name if lc.binding and hasattr(lc.binding, "model_name") else session.get("lollms_model_name", "unknown_model")
                    lc.generate_text(prompt=full_prompt_to_llm, images=llm_image_paths, stream=True, streaming_callback=llm_callback)
                except Exception as e_gen:
                    err_msg = f"LLM generation failed: {str(e_gen)}"
                    shared_state["generation_error"] = err_msg
                    main_loop.call_soon_threadsafe(stream_queue.put_nowait, json.dumps({"type": "error", "content": err_msg}) + "\n")
                finally: main_loop.call_soon_threadsafe(stream_queue.put_nowait, None)
            
            generation_thread = threading.Thread(target=blocking_call, daemon=True)
            generation_thread.start()
            while True:
                item = await stream_queue.get()
                if item is None: stream_queue.task_done(); break
                yield item; stream_queue.task_done()
            
            if generation_thread: generation_thread.join(timeout=10) # Increased timeout

            ai_response_content = shared_state["accumulated_ai_response"]
            ai_token_count = lc.count_tokens(ai_response_content) if ai_response_content else 0
            ai_parent_id = discussion_obj.messages[-1].id if discussion_obj.messages and discussion_obj.messages[-1].sender == lc.user_name else None

            if ai_response_content and not shared_state["generation_error"]:
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
            if generation_thread and generation_thread.is_alive(): print(f"WARNING: LLM gen thread for {username} still alive after timeout.")
            # Cleanup temporary original (non-moved) images that were not successfully moved
            if image_server_paths:
                user_temp_uploads_path = get_user_temp_uploads_path(username)
                for temp_rel_path in image_server_paths:
                    image_filename = Path(temp_rel_path).name
                    temp_abs_path = user_temp_uploads_path / image_filename
                    if temp_abs_path.exists(): # If it wasn't moved
                        background_tasks.add_task(temp_abs_path.unlink, missing_ok=True)


    return StreamingResponse(stream_generator(), media_type="application/x-ndjson")

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

    # Collect image assets to delete
    image_assets_to_delete = []
    if message_to_delete.image_references:
        disc_assets_path = get_user_discussion_assets_path(username) / discussion_id
        for ref in message_to_delete.image_references:
            asset_path = disc_assets_path / Path(ref).name
            if asset_path.is_file(): image_assets_to_delete.append(asset_path)

    if not discussion_obj.delete_message(message_id): # delete_message internal logic might change
        raise HTTPException(status_code=404, detail="Message deletion failed internally.") # Should be caught by earlier check
    
    save_user_discussion(username, discussion_id, discussion_obj)
    
    # Delete image assets from disk
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

    # Ensure target user session is loaded (important for get_user_lollms_client)
    # This is a bit of a hack; ideally, operations on other users shouldn't directly manipulate their live session
    # But for AppLollmsDiscussion, it needs a LollmsClient.
    # A better way would be to have a "system" LollmsClient or pass necessary configs.
    # For now, ensure target user session is primed if it's not there (won't persist past this request if target isn't logged in)
    if target_username not in user_sessions:
        # Prime with DB data
        initial_lollms_model_target = target_user_db.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name")
        llm_params_target = {
            "temperature": target_user_db.llm_temperature if target_user_db.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
            # ... other params ...
        }
        llm_params_target = {k: v for k, v in llm_params_target.items() if v is not None}
        user_sessions[target_username] = {
            "lollms_client": None, "safe_store_instances": {}, "discussions": {}, "discussion_titles": {},
            "lollms_model_name": initial_lollms_model_target, "llm_params": llm_params_target,
            "active_vectorizer": target_user_db.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
        }
        _load_user_discussions(target_username) # Load target's existing discussions into their session cache

    target_lc = get_user_lollms_client(target_username) # Get (or init) LC for target user
    new_discussion_id_for_target = str(uuid.uuid4())
    
    copied_discussion_obj = AppLollmsDiscussion(
        lollms_client_instance=target_lc,
        discussion_id=new_discussion_id_for_target,
        title=f"Sent: {original_discussion_obj.title}"
    )
    copied_discussion_obj.rag_datastore_id = None # RAG datastore selection is per-user/per-discussion

    # Copy messages and their assets
    sender_assets_path = get_user_discussion_assets_path(sender_username) / discussion_id
    target_assets_path = get_user_discussion_assets_path(target_username) / new_discussion_id_for_target
    
    if original_discussion_obj.messages:
        if sender_assets_path.exists() and any(msg.image_references for msg in original_discussion_obj.messages):
            target_assets_path.mkdir(parents=True, exist_ok=True)

    for msg in original_discussion_obj.messages:
        new_image_refs = []
        if msg.image_references:
            for img_ref_filename in msg.image_references: # img_ref is just filename.ext
                original_asset_file = sender_assets_path / img_ref_filename
                if original_asset_file.exists():
                    # Copy asset to target user's discussion assets
                    new_asset_filename = f"{uuid.uuid4().hex[:8]}_{img_ref_filename}" # Ensure unique name in target
                    target_asset_file = target_assets_path / new_asset_filename
                    try:
                        shutil.copy2(str(original_asset_file), str(target_asset_file))
                        new_image_refs.append(new_asset_filename) # Store new filename
                    except Exception as e_copy_asset:
                        print(f"ERROR copying asset {original_asset_file} for discussion send: {e_copy_asset}")
                else:
                    print(f"WARN: Asset {original_asset_file} for discussion send not found, skipping.")
        
        copied_discussion_obj.add_message(
            sender=msg.sender, content=msg.content,
            parent_message_id=msg.parent_message_id, # Keep parent IDs if meaningful structure
            binding_name=msg.binding_name, model_name=msg.model_name,
            token_count=msg.token_count, image_references=new_image_refs
        )
        # Note: Grades are NOT copied as they are user-specific.

    save_user_discussion(target_username, new_discussion_id_for_target, copied_discussion_obj)
    # Update target user's session cache if they are online
    if target_username in user_sessions:
         user_sessions[target_username]["discussions"][new_discussion_id_for_target] = copied_discussion_obj
         user_sessions[target_username]["discussion_titles"][new_discussion_id_for_target] = copied_discussion_obj.title

    return {"message": f"Discussion '{original_discussion_obj.title}' sent to user '{target_username}'."}


@discussion_router.post("/export", response_model=ExportData)
async def export_user_data(export_request: DiscussionExportRequest, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> ExportData:
    username = current_user.username
    user_db_record = db.query(DBUser).filter(DBUser.username == username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")

    user_settings = {
        "lollms_model_name": user_db_record.lollms_model_name,
        "safe_store_vectorizer": user_db_record.safe_store_vectorizer,
        "llm_temperature": user_db_record.llm_temperature,
        "llm_top_k": user_db_record.llm_top_k,
        "llm_top_p": user_db_record.llm_top_p,
        "llm_repeat_penalty": user_db_record.llm_repeat_penalty,
        "llm_repeat_last_n": user_db_record.llm_repeat_last_n,
    }
    
    # Datastores info
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

    # Handle imported user settings (e.g., apply if current user's settings are null)
    # This part is optional and depends on desired behavior.
    # For now, we just log them or display them.
    imported_user_settings = import_data.get("user_settings_at_export")
    if imported_user_settings:
        print(f"INFO: User settings from import file for user {import_data.get('exported_by_user', 'unknown')}: {imported_user_settings}")
        # Optionally, update current_user's settings if they are None
        # db_user_record = db.query(DBUser).filter(DBUser.id == user_id).first()
        # if db_user_record:
        # for key, value in imported_user_settings.items():
        # if hasattr(db_user_record, key) and getattr(db_user_record, key) is None and value is not None:
        # setattr(db_user_record, key, value)
        # db.commit() ... then re-init lollms_client if model changed.

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
            imported_discussion_obj.rag_datastore_id = disc_data_from_file.get("rag_datastore_id") # Import RAG datastore ID
                                                                                              # This ID might not be valid for the current user.
                                                                                              # Client UI should allow user to re-select a valid one.

            messages_from_file = disc_data_from_file.get("messages", [])
            target_assets_path = get_user_discussion_assets_path(username) / new_discussion_id
            
            if isinstance(messages_from_file, list):
                for msg_data_from_file in messages_from_file:
                    if isinstance(msg_data_from_file, dict) and "sender" in msg_data_from_file and "content" in msg_data_from_file:
                        imported_message_obj = AppLollmsMessage.from_dict(msg_data_from_file)
                        
                        # Image references in export are relative to that export's structure or original owner.
                        # For import, we don't automatically import assets. User would need to re-upload.
                        # So, clear image_references on import unless a more complex asset import is done.
                        imported_message_obj.image_references = [] # Simplification for now

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
    # UserAuthDetails already contains these from the session
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

    updated_params = False
    if params.llm_temperature is not None and db_user_record.llm_temperature != params.llm_temperature:
        db_user_record.llm_temperature = params.llm_temperature; updated_params = True
    if params.llm_top_k is not None and db_user_record.llm_top_k != params.llm_top_k:
        db_user_record.llm_top_k = params.llm_top_k; updated_params = True
    if params.llm_top_p is not None and db_user_record.llm_top_p != params.llm_top_p:
        db_user_record.llm_top_p = params.llm_top_p; updated_params = True
    if params.llm_repeat_penalty is not None and db_user_record.llm_repeat_penalty != params.llm_repeat_penalty:
        db_user_record.llm_repeat_penalty = params.llm_repeat_penalty; updated_params = True
    if params.llm_repeat_last_n is not None and db_user_record.llm_repeat_last_n != params.llm_repeat_last_n:
        db_user_record.llm_repeat_last_n = params.llm_repeat_last_n; updated_params = True

    if updated_params:
        try: db.commit()
        except Exception as e: db.rollback(); raise HTTPException(status_code=500, detail=f"DB error: {e}")
        # Update session and force LollmsClient re-init
        session_llm_params = user_sessions[username].get("llm_params", {})
        session_llm_params.update(params.model_dump(exclude_unset=True))
        user_sessions[username]["llm_params"] = session_llm_params
        user_sessions[username]["lollms_client"] = None 
        return {"message": "LLM parameters updated. Client will re-initialize."}
    return {"message": "No changes to LLM parameters."}

app.include_router(lollms_config_router)


# --- DataStore (RAG) API ---
datastore_router = APIRouter(prefix="/api/datastores", tags=["RAG DataStores"])

@datastore_router.post("", response_model=DataStorePublic, status_code=201)
async def create_datastore(ds_create: DataStoreCreate, current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> DBDataStore:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")
    
    # Check for unique name per user
    existing_ds = db.query(DBDataStore).filter_by(owner_user_id=user_db_record.id, name=ds_create.name).first()
    if existing_ds: raise HTTPException(status_code=400, detail=f"DataStore with name '{ds_create.name}' already exists for this user.")

    new_ds_db_obj = DBDataStore(
        owner_user_id=user_db_record.id,
        name=ds_create.name,
        description=ds_create.description
    )
    try:
        db.add(new_ds_db_obj); db.commit(); db.refresh(new_ds_db_obj)
        # Initialize the SafeStore file by calling get_safe_store_instance once
        # This will create the .db file on disk.
        get_safe_store_instance(current_user.username, new_ds_db_obj.id, db)
        
        # Construct public response model
        return DataStorePublic(
            id=new_ds_db_obj.id, name=new_ds_db_obj.name, description=new_ds_db_obj.description,
            owner_username=current_user.username, created_at=new_ds_db_obj.created_at, updated_at=new_ds_db_obj.updated_at
        )
    except IntegrityError: # Should be caught by earlier check, but as a safeguard
        db.rollback(); raise HTTPException(status_code=400, detail="DataStore name conflict (race condition).")
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error creating datastore: {e}")


@datastore_router.get("", response_model=List[DataStorePublic])
async def list_my_datastores(current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)) -> List[DataStorePublic]:
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not user_db_record: raise HTTPException(status_code=404, detail="User not found.")

    owned_datastores_db = db.query(DBDataStore).filter(DBDataStore.owner_user_id == user_db_record.id).order_by(DBSharedDataStoreLink.datastore.has.name).all()
    
    shared_links_db = db.query(DBSharedDataStoreLink).options(joinedload(DBSharedDataStoreLink.datastore).joinedload(DBDataStore.owner))\
        .filter(DBSharedDataStoreLink.shared_with_user_id == user_db_record.id).order_by(DBSharedDataStoreLink.datastore.has.name).all()

    response_list = []
    for ds_db in owned_datastores_db:
        response_list.append(DataStorePublic(
            id=ds_db.id, name=ds_db.name, description=ds_db.description,
            owner_username=current_user.username, # It's owned by current_user
            created_at=ds_db.created_at, updated_at=ds_db.updated_at
        ))
    for link in shared_links_db:
        ds_db = link.datastore
        # Avoid duplicates if a datastore is owned AND shared (shouldn't happen with current logic, but good practice)
        if not any(r.id == ds_db.id for r in response_list):
             response_list.append(DataStorePublic(
                id=ds_db.id, name=ds_db.name, description=ds_db.description,
                owner_username=ds_db.owner.username, # Get owner from relation
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

    # Check for name conflict if name is being changed
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
    
    # Get path before deleting DB record
    ds_file_path = get_datastore_db_path(current_user.username, datastore_id)
    ds_lock_file_path = Path(f"{ds_file_path}.lock")

    try:
        # Delete associated shared links first (or rely on cascade if configured strongly)
        db.query(DBSharedDataStoreLink).filter_by(datastore_id=datastore_id).delete(synchronize_session=False)
        db.delete(ds_db_obj)
        db.commit()
        
        # Remove from user session cache if present
        if current_user.username in user_sessions and datastore_id in user_sessions[current_user.username]["safe_store_instances"]:
            del user_sessions[current_user.username]["safe_store_instances"][datastore_id]

        # Delete the .db file and .lock file asynchronously
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
        # Update permission if different, or just confirm it's already shared
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
    except IntegrityError: # Should be caught by earlier check
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
    except ValueError: # Not an int, assume username
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
    ss = get_safe_store_instance(current_user.username, datastore_id, db) # Verifies access
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


@store_files_router.post("/upload-files") # User must be owner
async def upload_rag_documents_to_datastore(
    datastore_id: str, files: List[UploadFile] = File(...), vectorizer_name: str = Form(...),
    current_user: UserAuthDetails = Depends(get_current_active_user), db: Session = Depends(get_db)
) -> JSONResponse:
    if not safe_store: raise HTTPException(status_code=501, detail="SafeStore not available.")
    
    # Verify ownership for upload
    ds_record = db.query(DBDataStore).filter(DBDataStore.id == datastore_id).first()
    user_db_record = db.query(DBUser).filter(DBUser.username == current_user.username).first()
    if not ds_record or not user_db_record or ds_record.owner_user_id != user_db_record.id:
        raise HTTPException(status_code=403, detail="Only the owner can upload files to this DataStore.")

    ss = get_safe_store_instance(current_user.username, datastore_id, db) # Gets instance for owner
    
    # Store uploaded files within a subfolder for this datastore for clarity
    # e.g., data/<owner_username>/safestores_docs/<datastore_id>/<filename>
    # SafeStore itself will store the full path.
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
    ss = get_safe_store_instance(current_user.username, datastore_id, db) # Verifies access
    managed_docs = []
    try:
        with ss: stored_meta = ss.list_documents()
        # Filter to show only files that are within this datastore's expected document storage area
        # This logic might need adjustment based on how SafeStore stores file_path if multiple sources are added to one SafeStore DB.
        # Assuming add_document uses absolute paths from datastore_docs_path.
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
                except Exception: pass # Path resolution error
    except Exception as e: raise HTTPException(status_code=500, detail=f"Error listing RAG docs for datastore {datastore_id}: {e}")
    managed_docs.sort(key=lambda x: x.filename); return managed_docs


@store_files_router.delete("/files/{filename}") # User must be owner
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
    new_db_user = DBUser(
        username=user_data.username, hashed_password=hash_password(user_data.password), 
        is_admin=user_data.is_admin, 
        lollms_model_name=user_data.lollms_model_name or LOLLMS_CLIENT_DEFAULTS.get("default_model_name"),
        safe_store_vectorizer=user_data.safe_store_vectorizer or SAFE_STORE_DEFAULTS.get("global_default_vectorizer"),
        llm_temperature=user_data.llm_temperature if user_data.llm_temperature is not None else LOLLMS_CLIENT_DEFAULTS.get("temperature"),
        llm_top_k=user_data.llm_top_k if user_data.llm_top_k is not None else LOLLMS_CLIENT_DEFAULTS.get("top_k"),
        llm_top_p=user_data.llm_top_p if user_data.llm_top_p is not None else LOLLMS_CLIENT_DEFAULTS.get("top_p"),
        llm_repeat_penalty=user_data.llm_repeat_penalty if user_data.llm_repeat_penalty is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_penalty"),
        llm_repeat_last_n=user_data.llm_repeat_last_n if user_data.llm_repeat_last_n is not None else LOLLMS_CLIENT_DEFAULTS.get("repeat_last_n")
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
    
    user_data_dir_to_delete = get_user_data_root(user_to_delete.username) # Get path before DB delete

    try:
        # Delete owned datastores first (this will also delete their files via cascade or separate logic)
        # This is important because datastore files are outside the main user_data_dir if we mean to only delete APP_DATA_DIR / username
        # Actual datastore files are at APP_DATA_DIR / username / DATASTORES_DIR_NAME / <datastore_id>.db
        # The get_user_data_root will encompass these.
        
        # Remove user's session data
        if user_to_delete.username in user_sessions:
            del user_sessions[user_to_delete.username]

        db.delete(user_to_delete) # This should cascade to UserStarredDiscussion, UserMessageGrade, DataStore (owned), SharedDataStoreLink
        db.commit()
        
        # Asynchronously delete user's entire data directory
        if user_data_dir_to_delete.exists():
            background_tasks.add_task(shutil.rmtree, user_data_dir_to_delete, ignore_errors=True)
            
        return {"message": f"User '{user_to_delete.username}' and their data deleted."}
    except Exception as e:
        db.rollback(); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"DB error or file system error during user deletion: {e}")

app.include_router(admin_router)

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
    uvicorn.run("main:app", host=host, port=port, reload=False) # reload=True for dev
